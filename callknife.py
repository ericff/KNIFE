# python2.7 callknife.py 

 

#########################################################################
# PARAMETERS, I.E. INPUTS TO KNIFE CALL; need to add these here
#########################################################################

# dataset_name CANNOT HAVE ANY SPACES IN IT
dataset_name = "testData"

# run id to identify files in output, should change this each time
run_id = "nophred64"

mode = "skipDenovo"
read_id_style= "complete"
junction_overlap =  8
report_directory_name = "circReads"
ntrim= 40

# Not really used, just doing so it mimics test Data call
logstdout_from_knife = "logofstdoutfromknife"

##########################
### USAGE
############################

#sh completeRun.sh read_directory read_id_style alignment_parent_directory 
# dataset_name junction_overlap mode report_directory_name ntrim denovoCircMode 
# junction_id_suffix 2>&1 | tee out.log
# https://github.com/lindaszabo/KNIFE/tree/master/circularRNApipeline_Standalone

#########################################################################
# End of parameters
#########################################################################
 
import re, os, glob, subprocess

# first have to create directories (if they don't already exist)
#   and change file names and mv them to the right directories

# get current working dir

wdir = os.getcwd()
logfile = wdir + "/logknife3" + run_id + ".txt"

with open(logfile, 'w') as ff:
    ff.write(wdir)
    ff.write('\n\n\n')

    
# main directory to be used when running the knife:
# knifedir = "~/gl/circularRNApipeline_Standalone"
knifedir = "/src/knife/circularRNApipeline_Standalone"

try:                                         
    subprocess.check_call("cat /src/knife/circularRNApipeline_Standalone/findCircularRNA.sh >> " + logfile , shell=True)
except:
    with open(logfile, 'a') as ff:
        ff.write('Error in writing findCircularRNA.sh\n')

    
    
targetdir_list = [knifedir + "/index", knifedir + "/index", knifedir + "/denovo_scripts", knifedir + "/denovo_scripts/index"]
    
# check that there is a directory called circularRNApipeline_Standalone and all the subdirectories; there should be!

if not os.path.isdir(knifedir):
    os.makedirs(knifedir)
    
thisdir = targetdir_list[0]
if not os.path.exists(thisdir):
    os.makedirs(thisdir)

thisdir = targetdir_list[2]
if not os.path.exists(thisdir):
    os.makedirs(thisdir)

thisdir = targetdir_list[3]
if not os.path.exists(thisdir):
    os.makedirs(thisdir)

# Input file names are in an unusual format so they are easy to select when doing a run on
#   seven bridges. They should start in the home directory, as copies, because
#   they are entered as stage inputs.
#   Move them to the directories where KNIFE
#   expects them to be, then change their names.

# make function to do this for each of the four types of files
#  prefix is one of "infilebt1", "infilebt2", "infilefastas", or "infilegtf"
def move_and_rename(prefix, targetdir):
    globpattern = prefix + "*"
    matching_files = glob.glob(globpattern)
    if (len(matching_files)>= 1):
        for thisfile in matching_files:
            fullpatholdfile = wdir + "/" + thisfile
            fullpathnewfile = targetdir + "/" + re.sub(pattern=prefix, repl="", string= thisfile)
            subprocess.check_call(["mv", fullpatholdfile, fullpathnewfile])
            with open(logfile, 'a') as ff:
                ff.write('mv '+ fullpatholdfile + ' ' + fullpathnewfile + '\n')

#        os.rename(fullpatholdfile, fullpathnewfile)

prefix_list = ["infilebt2", "infilefastas", "infilegtf", "infilebt1"]

for ii in range(4):
    move_and_rename(prefix=prefix_list[ii], targetdir= targetdir_list[ii])

    
# cd into the knife directory
os.chdir(knifedir)

with open(logfile, 'a') as ff:
    ff.write('\n\n\n')
    subprocess.check_call(["ls", "-R"], stdout=ff)
    ff.write('\n\n\n')
    

# run test of knife
# sh completeRun.sh READ_DIRECTORY complete OUTPUT_DIRECTORY testData 8 phred64 circReads 40 2>&1 | tee out.log

try:
    with open(logfile, 'a') as ff:
        ff.write('\n\n\n')
        # changing so as to remove calls to perl:
        subprocess.check_call("sh completeRun.sh " + wdir + " " + read_id_style + " " + wdir + " " + dataset_name + " " + str(junction_overlap) + " " + mode + " " + report_directory_name + " " + str(ntrim) + " 2>&1 | tee " + logstdout_from_knife , stdout = ff, shell=True)
        # original test call:
        # subprocess.check_call("sh completeRun.sh " + wdir + " complete " + wdir + " testData 8 phred64 circReads 40 2>&1 | tee outknifelog.txt", stdout = ff, shell=True)
except:
    with open(logfile, 'a') as ff:
        ff.write('Error in running completeRun.sh')


#############################################################################
# tar all files in data set folder (but not Swapped files)  and its
#  subdirectories and tar them
# It WILL NOT output them with the directory structure, e.g. WITHOUT a top level folder
#   with the name of the aata set, e.g. these:
# I.e. it will NOT create a folder with a name
#   of the dataset like testData
# So this will unpack to several folders such as
#    circReads  logs  orig  sampleStats
# with no top level folder above them.
#############################################################################

datadirlocation = wdir + "/" + dataset_name  

# Change to wdir, then get all files in wdir/[dataset_name] folder, tar them.


os.chdir(wdir)
try:
    fullcall = "tar -cvzf " + dataset_name + "knifeoutputfiles" + run_id + ".tar.gz -C " + datadirlocation + " ." 
    with open(logfile, 'a') as ff:
        subprocess.check_call(fullcall, stderr=ff, stdout = ff, shell=True)
except:
    with open(logfile, 'a') as ff:
        ff.write("\nError in tarring the knife output files in the " + dataset_name + " directory\n")

#############################################################################
# Get two report files and tar and zip them
#  Technically looks for all files with names ending in .report.txt
# testData/circReads/combinedReports:
# -rw-r--r--@ 1 awk  staff    12M May 22 00:57 naiveinfSRR1027187_1_report.txt
#
# testData/circReads/reports:
# -rw-r--r--@ 1 awk  staff    12M May 22 00:04 infSRR1027187_1_report.txt
#
# Does not include the directory structure when tarring them
#############################################################################

os.chdir(wdir)


file_list = []
for root, subFolders, files in os.walk("."):
    for file in files:
        file_list.append(os.path.join(root,file))
        
try:
    text_file_list = filter(lambda x:re.search('report.txt$', x), file_list)
except:
    with open(logfile, 'a') as ff:
        ff.write("\nError in matching report.txt for the two text files\n")

try:
    text_file_list_without_paths = [os.path.basename(x) for x in text_file_list]
    text_file_dirs = [os.path.dirname(x) for x in text_file_list]
except:
    with open(logfile, 'a') as ff:
        ff.write("\nError in getting basenames or dirnames for the two text files\n")

try:
    for ii, thisfilename in enumerate(text_file_list_without_paths):
        if ii==0:
            fullcall = "tar -cvf " + dataset_name + "knifetextfiles" + run_id + ".tar -C "+ text_file_dirs[ii] + " " +  thisfilename
        elif ii>0:
            fullcall = "tar -rvf " + dataset_name + "knifetextfiles" + run_id + ".tar  -C " + text_file_dirs[ii]  +  " " + thisfilename
        subprocess.check_call(fullcall, shell=True)
except:
    with open(logfile, 'a') as ff:
        ff.write("\nError in tarring the two knife text output files in the " + dataset_name + " directory\n")

try:
    subprocess.check_call("gzip " + dataset_name + "knifetextfiles" + run_id + ".tar", shell=True)
except:
    with open(logfile, 'a') as ff:
        ff.write("\nProblem with gzipping.\n")
        
os.chdir(wdir)


        
#############################################################################
# OLD:
# tar all .txt files ONLY in data set folder (but not Swapped files)  and
#    its subdirectories and tar them
# ONLY TXT files
# do this by recursively looking for names of all text files, put those names
#  in file called tarlist in working directory, then use -T flag for tar
#
# It WILL output them with the directory structure, including a top level folder
#   with the name of the aata set, e.g. these:
# -rw-r--r--  0 root   root      454 May 22 00:43 testData/sampleStats/SampleAlignStats.txt
# -rw-r--r--  0 root   root      216 May 22 00:43 testData/sampleStats/SampleCircStats.txt
# -rw-r--r--  0 root   root 559959411 May 21 23:52 testData/orig/ids/genome/infSRR1027187_1_genome_output.txt
# ...
# 
#############################################################################

# Change to wdir, then get all TXT files in wdir/[dataset_name] folder, tar them.

# os.chdir(wdir)


# file_list = []
# for root, subFolders, files in os.walk(dataset_name):
#     for file in files:
#         file_list.append(os.path.join(root,file))
        
# text_file_list = filter(lambda x:re.search('.txt$', x), file_list)

# with open("tarlist", 'w') as ff:
#      ff.write('\n'.join([str(x) for x in text_file_list]))

# try:
#     fullcall = "tar -cvzf " + dataset_name + "knifetextfiles.tar.gz -T tarlist -C " + datadirlocation
#     subprocess.check_call(fullcall, shell=True)                                
# except:
#     with open(logfile, 'a') as ff:
#         ff.write("\nError in tarring the knife text output files in the " + dataset_name + " directory\n")


# Might want to get these??? Not sure what directory they are actually in, e.g.
#    maybe in wdir/testData/taskIdFiles/???             
# os.chdir(wdir)
# try:
#     subprocess.check_call("mv " + wdir + "/taskIdFiles/*.txt" + " " + wdir, shell=True)
# except:
#     with open(logfile, 'a') as ff:
#         ff.write('Error in moving taskIdFiles txt files.')


                        
     





        
