#!/usr/bin/env Rscript

## The heart of the GLM. Uses the text files of ids generated by the naive method run
# to assign reads to categories and outputs predictions per junction to glmReports. models
# are saved into glmModels for further manual investigation.

########## FUNCTIONS ##########

require(data.table)

# allows for variable read length (for trimmed reads)
getOverlapForTrimmed <- function(x, juncMidpoint=150){
    if (as.numeric(x["pos"]) > juncMidpoint){
      overlap = 0
    } else if (as.numeric(x["pos"]) + as.numeric(x["readLen"]) - 1 < juncMidpoint + 1){
      overlap = 0
    } else {
      overlap = min(as.numeric(x["pos"]) + as.numeric(x["readLen"]) - juncMidpoint, 
                    juncMidpoint + 1 - as.numeric(x["pos"]))
    }
  
  return(overlap)
}

addDerivedFields <- function(dt, useClass){
  if(nrow(dt) > 0){
    # calculate and add on cols for junction overlap, score adjusted for N penalties, 
    dt[,`:=`(is.pos=useClass,overlap=apply(dt, 1, getOverlapForTrimmed))]  # syntax for multiple :=
    # and length-adjusted alignment score (laplace smoothing so alignment score of 0 treated different for different length reads)
    dt[, lenAdjScore:=(as.numeric(aScore) - 0.001)/as.numeric(readLen)]
    dt[,`:=`(pos=NULL, aScore=NULL, numN=NULL, readLen=NULL)]
  }
  
  return(dt)
}

# the input file is just the file output by the circularRNApipeline under /ids
processClassInput <- function(classFile){
  cats = fread(classFile, header=TRUE, sep="\t")
  setkey(cats, id)
  
  return(cats)
}

# To avoid integer underflow issue when we have too many very small or very large probabilities.
# Take inverse of posterior probability, then take log, which simplifies to sum(log(q) - /sum(log(p))
# and then reverse operations to convert answer back to a probability.
# param p: vector of p values for all reads aligning to junction
# return posterior probability that this is a circular junction based on all reads aligned to it
getPvalByJunction <- function(p){
  out = tryCatch(
{
  q = 1-p
  x = sum(log(q)) - sum(log(p))  # use sum of logs to avoid integer underflow
  return(1/(exp(x) + 1))  # convert back to posterior probability
},
error = function(cond){
  print(cond)
  print(p)
  return("?")
},
warning = function(cond){
  print(cond)
  print(p)
  return("-")
}
  )
return(out)
}

applyToClass <- function(dt, expr) {
  e = substitute(expr)
  dt[,eval(e),by=is.pos]
}

applyToJunction <- function(dt, expr) {
  e = substitute(expr)
  dt[,eval(e),by=junction]
}

######## END FUNCTIONS, BEGIN WORK #########

args = commandArgs(trailingOnly = TRUE)
class_input = args[1]
data_out = args[2]
linear_juncp_out = args[3] 
circ_juncp_out = args[4]
print(paste("predict junctions called with args:", args))

#### SEPARATE READ CLASSES AND PARSE RELEVANT INFO ####

myClasses = processClassInput(class_input)
print(paste("class info processed", dim(myClasses)))

circ_reads = myClasses[(class %like% 'circ'), list(id, pos, qual, aScore, numN, readLen, junction)]
circ_reads = addDerivedFields(circ_reads, 1)

decoy_reads = myClasses[(class == 'decoy'), list(id, pos, qual, aScore, numN, readLen, junction)]
decoy_reads = addDerivedFields(decoy_reads, 0)

linear_reads = myClasses[(class %like% 'linear'), list(id, pos, qual, aScore, numN, readLen, junction)]
linear_reads = addDerivedFields(linear_reads, 1)

# clean up
rm(myClasses)

#### TRAIN EM ####

saves = list()  # to hold all of the glms for future use
max.iter = 2  # number of iterations updating weights and retraining glm

# set up data structure to hold per-junction predictions
junctionPredictions = linear_reads[, .N, by = junction] # get number of reads per junction
setnames(junctionPredictions, "N", "numReads")
setkey(junctionPredictions, junction)

# set up structure to hold per-read predictions
n.neg = nrow(decoy_reads) 
n.pos = nrow(linear_reads)
n.reads = n.neg+n.pos
class.weight = min(n.pos, n.neg)

readPredictions = rbindlist(list(linear_reads, decoy_reads))

# set initial weights uniform for class sum off all weights within any class is equal
if (n.pos >= n.neg){
  readPredictions[,cur_weight:=c(rep(n.neg/n.pos, n.pos), rep(1, n.neg))]
} else {
  readPredictions[,cur_weight:=c(rep(1, n.pos), rep(n.pos/n.neg, n.neg))]
}

# glm
for(i in 1:max.iter){
  # M step: train model based on current read assignments, down-weighting the class with more reads
  x = glm(is.pos~overlap+lenAdjScore+qual, data=readPredictions, family=binomial(link="logit"), weights=readPredictions[,cur_weight])
  saves[[i]] = x

  # get CI on the output probabilities and use 95% CI
  preds = predict(x, type = "link", se.fit = TRUE)
  critval = 1.96 # ~ 95% CI
  upr = preds$fit + (critval * preds$se.fit)
  lwr = preds$fit - (critval * preds$se.fit)
  upr2 = x$family$linkinv(upr)
  lwr2 = x$family$linkinv(lwr)
  
  # use the upper 95% value for decoys and lower 95% for linear
  adj_vals = c(rep(NA, n.reads))
  adj_vals[which(readPredictions$is.pos == 1)] = lwr2[which(readPredictions$is.pos == 1)]
  adj_vals[which(readPredictions$is.pos == 0)] = upr2[which(readPredictions$is.pos == 0)]
  x$fitted.values = adj_vals  # so I don't have to modify below code
  
  # report some info about how we did on the training predictions
  totalerr = sum(abs(readPredictions[,is.pos] - round(x$fitted.values)))
  print (paste(i,"total reads:",n.reads))
  print(paste("both negative",sum(abs(readPredictions[,is.pos]+round(x$fitted.values))==0), "out of ", n.neg))
  print(paste("both positive",sum(abs(readPredictions[,is.pos]+round(x$fitted.values))==2), "out of ", n.pos))
  print(paste("classification errors", totalerr, "out of", n.reads, totalerr/n.reads ))
  print(coef(summary(x)))
  readPredictions[, cur_p:=x$fitted.values] # add this round of predictions to the running totals
  
  # calculate junction probabilities based on current read probabilities and add to junction predictions data.table
  tempDT = applyToJunction(subset(readPredictions, is.pos == 1), getPvalByJunction(cur_p))
  setnames(tempDT, "V1", paste("iter", i, sep="_"))
  setkey(tempDT, junction)
  junctionPredictions = junctionPredictions[tempDT]  # join junction predictions and the new posterior probabilities
  rm(tempDT)  # clean up
  
  # E step: weight the reads according to how confident we are in their classification. Only if we are doing another loop
  if(i < max.iter){
    posScale = class.weight/applyToClass(readPredictions,sum(cur_p))[is.pos == 1,V1]
    negScale = class.weight/(n.neg - applyToClass(readPredictions,sum(cur_p))[is.pos == 0,V1])
    readPredictions[is.pos == 1,cur_weight:=cur_p*posScale]
    readPredictions[is.pos == 0,cur_weight:=((1 - cur_p)*negScale)]
  }
  setnames(readPredictions, "cur_p", paste("iter", i, sep="_")) # update names
}  

# calculate mean and variance for null distribution
read_pvals = readPredictions[,iter_2]
posteriors = log((1-read_pvals)/read_pvals) 
use_mu = mean(posteriors)
use_var=var(posteriors)

# add p-value to junctionPredictions 
junctionPredictions[, p_value:=(pnorm(log(1/iter_2 - 1) - numReads*use_mu)/sqrt(numReads*use_var))]

# rename cols to be consistent with circular glmReports
junctionPredictions[, iter_1:=NULL]
setnames(junctionPredictions, "iter_2", "p_predicted")

save(saves, file=data_out)  # save models
write.table(junctionPredictions, linear_juncp_out, row.names=FALSE, quote=FALSE, sep="\t")

#### PREDICT CIRCULAR JUNCTIONS ####

# use the last training model (still in variable x) to predict on the circles 
preds = predict(x, newdata=circ_reads, type = "link", se.fit = TRUE) 

lwr = preds$fit - (1.96 * preds$se.fit)  # ~ lower 95% CI to be conservative 
circ_reads[, p_predicted:=x$family$linkinv(lwr)] # add lower 95% CI prediction

junctionPredictions = circ_reads[, .N, by = junction] # get number of reads per junction
setnames(junctionPredictions, "N", "numReads")
setkey(junctionPredictions, junction)

# calculate junction probabilities based on predicted read probabilities
tempDT = applyToJunction(circ_reads, getPvalByJunction(p_predicted))
setkey(tempDT, junction)
junctionPredictions = junctionPredictions[tempDT]  # join junction predictions and the new posterior probabilities
setnames(junctionPredictions, "V1", "p_predicted")

# add p-value to junctionPredictions (see pdf on Julia's blog with logic for this)
read_pvals = circ_reads[,p_predicted]
posteriors = log((1-read_pvals)/read_pvals) 
use_mu = mean(posteriors)
use_var=var(posteriors)
junctionPredictions[, p_value:=(pnorm(log(1/p_predicted -1) - numReads*use_mu)/sqrt(numReads*use_var))]

rm(tempDT)  # clean up

write.table(junctionPredictions, circ_juncp_out, row.names=FALSE, quote=FALSE, sep="\t")



