#!/usr/bin/env python
import pandas, re, logging, os
pandas.set_option('display.max_rows', 500)
pandas.set_option('display.max_columns', 500)
pandas.set_option('display.width', 1000)
import subprocess
from argparse import ArgumentParser
from ete3 import NCBITaxa, TreeStyle
from collections import Counter,OrderedDict

#pandas.options.display.float_format = '{:.1E}'.format #render scientific notation

#default init arguments
args=ArgumentParser()
# args.multi_match = True
# args.exact_match = None
# args.loose_match = None
# args.render_tree = True
# args.write_newick = True
# args.debug = False
# args.relaxase_accession = None
# args.outdir = "./"
# args.inputseq = False

#OUTDIR = os.getcwd()+"/"

# def createLogger():
#     log = logging.getLogger('MOB-Suite')
#     formatter = logging.Formatter(
#         '%(asctime)s %(name)-12s %(message)s')
#     log.setLevel(logging.DEBUG)
#
#     console = logging.StreamHandler()
#     console.setFormatter(formatter)
#     console.setLevel(logging.DEBUG)
#     log.addHandler(console)
#     return log

#LOG = createLogger()
def loadliteratureplasmidDB():
    return  pandas.read_csv(os.path.dirname(os.path.abspath(__file__))+"/databases/host_range_literature_plasmidDB.csv",sep=",",encoding = "ISO-8859-1")

def findHitsInLiteratureDBbyReplicon(replicon_names,plasmid_lit_db):
    """
    Get me the indices/hits per each replicon name and adjust if the replicon name returns no hit, then use inc family search
    :param replicon_names: names of inc replicons (e.g. IncFII)
    :param plasmid_lit_db: pandas dataframe with all literature information on plasmids
    :return: repliconsearchdict: dictionary replicon name / hit indices (i.e. rows) (e.g. {'IncF': [0, 1, 2, 3, 4, 5, 6, 7, 97, 123, 135]})
    """
    repliconsearchdict = {}
    for replicon_name in replicon_names:
        idx = [i for i in range(0, plasmid_lit_db.shape[0]) if plasmid_lit_db.iloc[i, :]["Replicon"] == replicon_name]
        # search literature database by replicon family (e.g. IncF) if no results are returned
        if len(idx) == 0:
            replicon_name = re.findall("Inc[A-Z]{1}|ColRNA", replicon_name)[0]  # if exact match failed, search by replicon family
            idx = [i for i in range(0, plasmid_lit_db.shape[0]) if
                   len(re.findall(replicon_name, plasmid_lit_db.iloc[i, :]["Replicon"])) != 0]
        repliconsearchdict[replicon_name] = idx
    return repliconsearchdict

def getLiteratureBasedHostRange(replicon_names,plasmid_lit_db,input_seq=""):
    '''
    # Read literature-based database file
    # Make HR prediction based on the literature evidence on replicon and mob-suite cluster
    # If replicon is not know or mash dist to the nearest reference sequence is > 0.05 ... do not do any prediction
    # Indicate if the plasmid is broad or narrow range class
    :param replicon_name: replicon name based on Inc typing (e.g. IncP)
    :param plasmid_lit_db: pandas dataframe representing a database of well curated plasmid mentioned in the literature
    :param input_seq: path to the input plasmid sequence
    :return: report_df: pandas dataframe with all relevant information on the input query including literature reported host range and typical plasmids and PMIDs
             lit_taxids: list of taxonomy ids
    '''


    report_df=pandas.DataFrame()
    repliconsearchdict = findHitsInLiteratureDBbyReplicon(replicon_names,plasmid_lit_db)
    lit_taxids_list=[]
    #report_dict=dict.fromkeys(['apple','ball'],"-")

    for replicon_name in repliconsearchdict.keys():
        #find hits in database based on replicon query
        idx = repliconsearchdict[replicon_name]
        literature_knowledge = plasmid_lit_db.iloc[idx,:].copy() # makring sure the new data frame is created

        if literature_knowledge.shape[0] == 0:
            continue
            #raise Exception("Could not extract any information from the literature database matching the search")

        #data type conversion
        #literature_knowledge["TransferRate"] = pandas.to_numeric(literature_knowledge["TransferRate"])

        literature_knowledge.loc[:,"TransferRate"] = literature_knowledge.loc[:,"TransferRate"].astype(float)
        literature_knowledge.loc[literature_knowledge["Size"].isna() == False, "Size"] = literature_knowledge.loc[literature_knowledge["Size"].isna()== False, "Size"].astype(int)
        literature_knowledge.loc[literature_knowledge["Year"].isna() == False, "Year"] = literature_knowledge.loc[literature_knowledge["Year"].isna() == False, "Year"].astype(int)
        literature_knowledge.loc[:,"PMID"] = literature_knowledge.loc[:,"PMID"].astype(int)

        #print(literature_knowledge)
        #print(literature_knowledge.loc[:,["HostRangeRankClaim","PMID"]])

        #print(literature_knowledge.loc[:,"PMID"])
        #print(literature_knowledge.dtypes)
        #exit()
        #phylolitertree = getTaxonomyTree()
        #remove any entries that are map to uncultured bacteria (avoids inflation of the host range)
        select_vector = [True if len(re.findall("uncultured", line)) == 0 else False for line in literature_knowledge["Species"]]
        lit_taxids=list(set(literature_knowledge.loc[select_vector,"taxid"]))
        rank,rankname = getHostRangeRankCovergence(lit_taxids)

        host_range_literature_claim=[] #what does the papers claim in terms of the host range?
        for pid in set(literature_knowledge.loc[:,"PMID"]):
            hr_lit_claim = literature_knowledge[literature_knowledge["PMID"] == pid][["HostRangeRankClaim","PMID","PMCID"]]
            #print(hr_lit_claim)
            #print(hr_lit_claim["HostRangeRankClaim"].values[0],hr_lit_claim["PMID"].values[0],hr_lit_claim["PMID"].isna().values)
            host_range_literature_claim.append(str(hr_lit_claim["HostRangeRankClaim"].values[0]))
            #if hr_lit_claim["HostRangeRankClaim"].isna().values[0] == False and hr_lit_claim["PMID"].isna().values[0] == False :
            #    host_range_literature_claim.append(str(hr_lit_claim["HostRangeRankClaim"].values[0])+" (PMID:"+str(hr_lit_claim["PMID"].values[0])+")")
            #elif hr_lit_claim["HostRangeRankClaim"].isna().values[0] == False and hr_lit_claim["PMCID"].isna().values[0] == False:
            #    host_range_literature_claim.append(str(hr_lit_claim["HostRangeRankClaim"].values[0]) + " (PMCID:" + str(hr_lit_claim["PMCID"].values[0]) + ")")

        host_range_literature_claim = Counter(host_range_literature_claim).most_common(1)[0][0] #get the most common host range rank hit
        hostrangeclassdict = Counter(literature_knowledge["HostRangeClass"])
        HostRangeClass = [key for key in hostrangeclassdict.keys()  if  hostrangeclassdict[key] == max(hostrangeclassdict.values())]

        if any(literature_knowledge["TransferRate"] > 0):
            LiteratureMinTransferRateRange = min([i for i in literature_knowledge["TransferRate"] if i >= 0])
            LiteratureMeanTransferRateRange = mean([i for i in literature_knowledge["TransferRate"] if i >= 0])
            LiteratureMaxTransferRateRange = max([i for i in literature_knowledge["TransferRate"] if i >= 0])
        else:
            LiteratureMinTransferRateRange  = "NA"
            LiteratureMaxTransferRateRange  = "NA"
            LiteratureMeanTransferRateRange = "NA"

        report_dict = OrderedDict({  "LiteratureQueryReplicon": ",".join(replicon_names),
                         "LiteratureSearchReplicon": replicon_name,
                         "LiteratureFoundPlasmidsNames": ",".join(set(literature_knowledge["Plasmid_Name"])),
                         "LiteratureFoundPlasmidsNumber": len(set(literature_knowledge["Plasmid_Name"])),
                         "LiteratureReportedHostRangePlasmidClass": HostRangeClass,
                         "LiteratureReportedHostPlasmidSpecies": ",".join(set(literature_knowledge["Species"])),
                         "LiteratureReportedPlasmidHostSpeciesNumber": len(set(literature_knowledge["Species"])),
                         "LiteraturePredictedDBHostRangeTreeRank": [rank],
                         "LiteraturePredictedDBHostRangeTreeRankSciName": [rankname],
                         "LiteratureReportedHostRangeInPubs": [host_range_literature_claim],
                         "LiteratureMinTransferRateRange": [LiteratureMinTransferRateRange],
                         "LiteratureMaxTransferRateRange": [LiteratureMaxTransferRateRange],
                         "LiteratureMeanTransferRateRange": [LiteratureMeanTransferRateRange],
                         "LiteraturePMIDs": ";".join(set([str(i) for i in literature_knowledge.loc[:, "PMID"]])),
                         "LiteraturePublicationsNumber": len(set(literature_knowledge.loc[:, "PMID"]))})

        #if input plasmid sequence is provided, do additional closest match based on the sequence similarity and append to the general report

        if input_seq.strip():  #if plasmid sequence is available
            literature_accession_top_hit, literature_mash_dist_top_hit = getClosestLiteratureRefPlasmid(input_seq)
            #print("L",literature_accession_top_hit, literature_mash_dist_top_hit,literature_accession_top_hit.rsplit("."))
            #print(plasmid_lit_db["NCBI_Accession"])
            #print()
            #by accession search
            #idx = [i for i in range(0, len(literature_knowledge)) if len(re.findall(literature_accession_top_hit.rsplit(".")[0],plasmid_lit_db["NCBI_Accession"].values[i])) != 0]
            literature_closest_seq_hit_df = plasmid_lit_db[plasmid_lit_db["NCBI_Accession"] == literature_accession_top_hit.rsplit(".")[0]]
            if literature_closest_seq_hit_df.empty:
                exit("Literatire top hit search failed! Check mash top hit return from the getClosestLiteratureRefPlasmid()")


            report_dict.update(OrderedDict({"LiteratureClosestRefrencePlasmidAcc":[literature_accession_top_hit],
                                "LiteratureClosestPlasmidName":literature_closest_seq_hit_df.loc[:,"Plasmid_Name"].values[0],
                                "LiteratureClosestPlasmidSize": int(literature_closest_seq_hit_df.loc[:,"Size"].values[0]),
                                "LiteratureClosestMashDistance": [literature_mash_dist_top_hit]}))

        #append results from different replicons (if multiple are present)
        report_df = pandas.concat([report_df, pandas.DataFrame.from_dict(report_dict)])
        lit_taxids_list = lit_taxids + lit_taxids

    return report_df, lit_taxids_list
    #report_table.to_csv(args.outputprefix+'_literature_report.txt',sep="\t",
    #                    float_format='%.1E', index=False, na_rep="NA",mode="w")

def collapseLiteratureReport(df):
    """
    Aggregate data for easier reporting averaging and maximizing fields
    :param: df: dataframe returned from literature report with the following columns
    #publications	LiteratureClosestRefrencePlasmid	LiteratureClosestPlasmidName	ClosestLiteraturePlasmidSize	LiteratureClosestMashDistance
    :return: single row dataframe
    """

    collapsedlitdf=pandas.DataFrame.from_records([],columns=df.columns,index=[0])

    conversiondict={"NarrowHostRange":1,"WideHostRange":2,"BroadHostRange":3}

    #no rank;no rank;superkingdom;phylum;class;order;family;genus;species group;species
    rankconversiondict={"species":1,"genus":2,"family":3,"order":4,"class":5,"phylum":6,"superkingdom":7}
    numrank2nameconversiondict = {1:"species", 2:"genus",3:"family",4:"order",5:"class", 6:"phylum",7:"superkingdom"}


    collapsedlitdf.loc[0,"LiteratureQueryReplicon"] = df.loc[0,"LiteratureQueryReplicon"]
    collapsedlitdf.loc[0, "LiteratureSearchReplicon"] = ",".join(df.loc[:,"LiteratureSearchReplicon"].values)
    collapsedlitdf.loc[0, "LiteratureFoundPlasmidsNames"] = ",".join(df.loc[:,"LiteratureFoundPlasmidsNames"].values)
    collapsedlitdf.loc[0,"LiteratureFoundPlasmidsNumber"]=sum(df.loc[:, "LiteratureFoundPlasmidsNumber"])
    hrclassnum = max([conversiondict[k] for k in set(df.loc[:, "LiteratureReportedHostRangePlasmidClass"].values)])
    collapsedlitdf.loc[0, "LiteratureReportedHostRangePlasmidClass"] = [k for k in conversiondict if conversiondict[k] == hrclassnum][0]
    collapsedlitdf.loc[0,"LiteratureReportedHostPlasmidSpecies"]=",".join(set(df.loc[:,"LiteratureReportedHostPlasmidSpecies"].values.tolist()[0].split(",")))
    collapsedlitdf.loc[0, "LiteratureReportedPlasmidHostSpeciesNumber"] = len(set(df.loc[:,"LiteratureReportedHostPlasmidSpecies"].values.tolist()[0].split(",")))
    hrtreeranknum = max([rankconversiondict[k] for k in df.loc[:, "LiteraturePredictedDBHostRangeTreeRank"].values])
    collapsedlitdf.loc[0,"LiteraturePredictedDBHostRangeTreeRank"] = [k for k in rankconversiondict if rankconversiondict[k] == hrtreeranknum][0]
    idx=df.loc[:,"LiteraturePredictedDBHostRangeTreeRank"] == collapsedlitdf.loc[0,"LiteraturePredictedDBHostRangeTreeRank"]
    collapsedlitdf.loc[0,"LiteraturePredictedDBHostRangeTreeRankSciName"] = df[idx]["LiteraturePredictedDBHostRangeTreeRankSciName"].values[0]
    collapsedlitdf.loc[0,"LiteratureReportedHostRangeInPubs"] = numrank2nameconversiondict[max([rankconversiondict[k] for k in df.loc[:, "LiteratureReportedHostRangeInPubs"].values])]

    for field in ["LiteratureMinTransferRateRange","LiteratureMaxTransferRateRange", "LiteratureMeanTransferRateRange"]:
        if all(df[field].isna()):
            collapsedlitdf.loc[0, field] = "NaN"
        else:
            collapsedlitdf.loc[0,field] = mean(df[df[field].isna() == False][field].values)

    collapsedlitdf.loc[0,"LiteraturePMIDs"] = ";".join(df["LiteraturePMIDs"])
    collapsedlitdf.loc[0, "LiteraturePublicationsNumber"] = sum(df["LiteraturePublicationsNumber"])

    #the closest sequence based result will the only one, no need to collapse, just copy
    if [col for col in df.columns if col == "LiteratureClosestRefrencePlasmidAcc"]:
        for field in ['LiteratureClosestRefrencePlasmidAcc', 'LiteratureClosestPlasmidName', 'LiteratureClosestPlasmidSize', 'LiteratureClosestMashDistance']:
            collapsedlitdf.loc[0, field] = df.loc[0,field]

    return(collapsedlitdf)

def getClosestLiteratureRefPlasmid(input_fasta):
    """
    In cases when plasmid sequence is available run additional sequence-based query of the plasmid reference to
    find closest representative plasmid at < 0.05 mash distance. Since plasmids are genomics puzzles of fragements,
    k-mer based approach of distance estimataion might be of benefit in contrast to more deterministic BLAST-based approaches
    :param query single contig sequence in FASTA format
    :return: closest literature curated plasmid accession number and mash distance between query and reference
    """
    reference_db=os.path.dirname(os.path.abspath(__file__))+"/databases/literature_mined_plasmid_seq_db.fasta.msh"
    #input_fasta="/Users/kirill/WORK/MOBSuiteHostRange2018/Source/mob-suite/mob_suite/tests/TestData/IncF/ET11_Ecoli_plasmid_529.fasta"
    p = subprocess.Popen(["mash dist -p 1 "+reference_db+" "+input_fasta],stdout=subprocess.PIPE, shell=True)
    stdout = p.communicate()[0].decode("utf-8")

    records = list()
    for line in stdout.split('\n'):
        items=line.rsplit("\t")
        if len(items) != 1:
            records.append((items))

    mash_dist_df = pandas.DataFrame.from_records(records,columns=["Accession","QueryID","mash_dist","p-value","shared_hashes"])
    top_hit_df = mash_dist_df[mash_dist_df.loc[:, "mash_dist"] == min(mash_dist_df.loc[:, "mash_dist"])]
    return top_hit_df.loc[:,"Accession"].values[0], top_hit_df.loc[:, "mash_dist"].values[0]



def mean(numbers):
    return float(sum(numbers)) / max(len(numbers), 1)

def getHostRangeRankCovergence(taxids):
    """
    :param taxids - list of taxonomy ids allowing to build a tree
    :return rank - taxonomic rank at which phylogenetic tree branches converge
    :return sci_name - taxonomic rank name at which phylogenetic tree branches converge
    """
    from ete3 import NCBITaxa, TreeStyle
    ncbi = NCBITaxa()
    #taxids=[562,573,1288825,439842]
    tree = ncbi.get_topology(taxids)
    tree.annotate_ncbi_taxa(taxid_attr='name')
    return(tree.rank,tree.sci_name)


#the main function to process
def getRefSeqHostRange(replicon_name_list,  mob_cluster_id, relaxase_name_acc_list, relaxase_name_list, matchtype, hr_obs_data):
    """
    Get NCBI RefSeq host range based on the search parameters either/or replicon, mob_cluster_id, relaxase family, relaxase accession
    :param replicon_name_list: a list of replicons to process ['IncP','IncF']
    :param mob_cluster_id:  mob-cluster cluster id
    :param relaxase_name_acc_list:  a list of MOB accession ids ['NC_017627_00068' 'NC_011416_00039']
    :param relaxase_name_list: relaxase family names list ['MOBF' 'MOBP']
    :param matchtype: how we will match fields in the database (exactly = entire field, multi = query might represent part of the field)
    :param hr_obs_data: host range observed data
    :return: convergance_rank: effectively the host range approximated by the convergance rank on the phylogenetic tree
             converged_taxonomy_name: the host range name given by the convergence rank
             unique_ref_selected_taxids: a list of reference taxids that matched the query
             ref_taxids_df: pandas dataframe with the key information on the host range
             stats_host_range_dict: dictionary on the number of hits per the each node of the resulting host range phylogenetic tree
    """


    logging.debug("Inside getRefSeqHostRange()")
    logging.debug("replicon_name_list:%s\nmob_cluster_id:%s\n%srelaxase_name_acc_list:%s\nrelaxase_name_list:%s\n",
                  replicon_name_list,mob_cluster_id,relaxase_name_acc_list,relaxase_name_list,matchtype) #DEBUG



    if mob_cluster_id != None:
        mob_cluster_id=str(mob_cluster_id) #make sure it is a string

    logging.info("Loading the plasmid reference database ...")

    #load reference lookup table
    ref_taxids_df = pandas.DataFrame()


    logging.info("Searching  RefSeq plasmid database ...")

    if replicon_name_list is not None:
        for replicon_name in replicon_name_list:
            n_total_records_before = ref_taxids_df.shape[0]
            logging.debug("Replicon name: {} MOB-Cluster: {}\n".format(replicon_name, mob_cluster_id))
            ref_taxids_df = pandas.concat([ref_taxids_df,getHostRangeDBSubset(hr_obs_data, replicon_name, "Ref_rep_type(s)", matchtype)])
            logging.debug("Extracted records (replicon): {}".format(ref_taxids_df.shape[0] - n_total_records_before))
    if mob_cluster_id is not None:
        ref_taxids_df = pandas.concat([ref_taxids_df, getHostRangeDBSubset(hr_obs_data, mob_cluster_id, "Ref_cluster_id", matchtype)])
        logging.debug("Extracted total records (clusterid): {}".format(ref_taxids_df.shape[0]))
    if relaxase_name_acc_list is not None:
        for relaxase_name_acc in relaxase_name_acc_list:
            ref_taxids_df = pandas.concat([ref_taxids_df,getHostRangeDBSubset(hr_obs_data, relaxase_name_acc, "Ref_relaxase_type_accession(s)",matchtype)])
            logging.debug("Relaxase accession: {}\n".format(relaxase_name_acc))
    if relaxase_name_list is not None:
        for relaxase_name in relaxase_name_list:
            ref_taxids_df = pandas.concat([ref_taxids_df, getHostRangeDBSubset(hr_obs_data, relaxase_name, "Ref_relaxase_type(s)", matchtype)])
    if ref_taxids_df.empty:
        logging.error("RefSeq Plasmid database returned no hits perhaps due to no search paramenters specified (i.e. replicon, mob_cluster_id, relaxase family, relaxase accession #).")
        logging.error("Search parameters:\
                       replicon name list: "+str(replicon_name_list)+"; mob_cluster_id: "+
                       str(mob_cluster_id)+"; relaxase_name_acc_list: "+
                       str(relaxase_name_acc_list)+"; relaxase_name_list: "+str(relaxase_name_list)+";")
        raise Exception("Empty dataframe returned from RefSeq plasmid database")


    #select subset of ref data based on criteria (e.g. replicon name)
    # if replicon_name_list != None and mob_cluster_id != None and relaxase_name_acc_list == None and relaxase_name_list == None:
    #
    #     #replicon_name="IncI1"; mob_cluster_id="476"
    #     for replicon_name in replicon_name_list:
    #         n_total_records_before = ref_taxids_df.shape[0]
    #         logging.debug("Replicon name: {} MOB-Cluster: {}\n".format(replicon_name, mob_cluster_id))
    #         ref_taxids_df = pandas.concat([ref_taxids_df,getHostRangeDBSubset(hr_obs_data, replicon_name, "Ref_rep_type(s)", matchtype)])
    #         logging.debug("Extracted records (replicon): {}".format(ref_taxids_df.shape[0] - n_total_records_before))
    #
    #     #merge with cluster_id results too
    #     ref_taxids_df = pandas.concat([ref_taxids_df,getHostRangeDBSubset(hr_obs_data, mob_cluster_id, "Ref_cluster_id", matchtype)])
    #     logging.debug("Extracted total records (clusterid): {}".format(ref_taxids_df.shape[0]))
    #
    # elif replicon_name_list != None and mob_cluster_id == None and relaxase_name_acc_list != None and relaxase_name_list == None:
    #     for replicon_name in replicon_name_list:
    #         logging.debug("Replicon name: {}".format(replicon_name))
    #         ref_taxids_df = pandas.concat([ref_taxids_df, getHostRangeDBSubset(hr_obs_data, replicon_name, "Ref_rep_type(s)", matchtype)])
    #     for relaxase_name_acc in relaxase_name_acc_list:
    #         ref_taxids_df = pandas.concat([ref_taxids_df,getHostRangeDBSubset(hr_obs_data, relaxase_name_acc, "Ref_relaxase_type(s)",matchtype)])
    #         logging.debug("Relaxase accession: {}\n".format(relaxase_name_acc))
    #
    # elif replicon_name_list != None and mob_cluster_id == None and relaxase_name_acc_list == None and relaxase_name_list == None:
    #     for replicon_name in replicon_name_list:
    #         n_total_records_before = ref_taxids_df.shape[0]
    #         logging.debug("Replicon name: {}\n".format(replicon_name, mob_cluster_id))
    #         ref_taxids_df = pandas.concat([ref_taxids_df, getHostRangeDBSubset(hr_obs_data, replicon_name, "Ref_rep_type(s)", matchtype)])
    #         logging.debug("Extracted records (replicon): {}".format(ref_taxids_df.shape[0]-n_total_records_before))
    #
    # elif replicon_name_list == None and mob_cluster_id == None and relaxase_name_list != None:
    #     for relaxase_name in relaxase_name_list:
    #         ref_taxids_df = pandas.concat([ref_taxids_df, getHostRangeDBSubset(hr_obs_data, relaxase_name, "Ref_relaxase_type(s)", matchtype)])
    #
    #     ref_taxids_df = getHostRangeDBSubset(hr_obs_data, relaxase_name_acc, "Ref_relaxase_type(s)", matchtype)
    # elif replicon_name_list == None and mob_cluster_id != None and relaxase_name_acc == None:
    #     print("MOBClusterID: {}".format(mob_cluster_id))
    #     ref_taxids_df = getHostRangeDBSubset(hr_obs_data, mob_cluster_id, "Ref_cluster_id", matchtype)
    # elif relaxase_name_list != None:
    #     print("Relaxase Accession: {}".format(args.relaxase_accession))
    #     ref_taxids_df = getHostRangeDBSubset(hr_obs_data, args.relaxase_accession, "Ref_relaxase_type_accession(s)", matchtype)
    # else:
    #     logging.error("No search paramenters specified (i.e. replicon, mob_cluster_id, relaxase family, relaxase accession #).")
    #     exit("Missing ref plasmid database search parameters (e.g. replicon, relaxases, clusterID)")

    unfiltered_n_ref_hits = ref_taxids_df.shape[0]
    #QC: remove uncultured reference database hits as they thend to inflate host range
    select_vector=[True if len(re.findall("uncultured",line)) == 0 else False for line in ref_taxids_df["lineage_names"] ]
    ref_taxids_df=ref_taxids_df[select_vector]


    # Check if the search returned no results. Abort
    n_ref_rep_hits = ref_taxids_df.shape[0]  # number of records on the query replicon/relaxase
    logging.debug("QC removed {} hits (uncultured bacteria filter)".format(unfiltered_n_ref_hits - n_ref_rep_hits))

    if n_ref_rep_hits == 0:
        logging.error("ERROR: No hits were found ...")
        exit("ERROR: No plasmid reference database hits were found ... Try --loose_match parameter")


    #do some stats on the returned records
    ref_taxids = list(ref_taxids_df['taxid']) #might be duplicated taxids
    unique_ref_selected_taxids = set(list(ref_taxids_df['taxid'])) #UNIQUE taxids returned as per query

    logging.debug("Found {} records (with duplicates) in the reference database.({} unique and {} duplicated)".format(n_ref_rep_hits, \
                                                                                                                 len(unique_ref_selected_taxids),
                                                                                                                 n_ref_rep_hits-len(unique_ref_selected_taxids)))

    convergance_rank, converged_taxonomy_name = getHostRangeRankCovergence(ref_taxids)
    #ref_taxids_str = ",".join(str(t) for t in sorted(unique_ref_taxids))


    #counts_per_ref_taxid_dict = Counter(ref_taxids_df['taxid']) #Counter({562: 66, 624: 10, 573: 6} #where key is taxid


    # #read selected taxonomy lineages from the reference file

    #create dictionary of ranks and taxnomy names for each reference database extracted lineage
    taxonony_lineages_dict_list = list()
    for key in ref_taxids:
         selection_idx = list(ref_taxids_df['taxid'] == key)
         #taxid2species = ref_taxids_df.loc[selection_idx]['Organism'].iloc[0]
         #print("Taxid:{}\tHits:{}\tOrganism:{}".format(key,value,taxid2species))
         tax_lineage_name_list = (ref_taxids_df.loc[selection_idx]['lineage_names'].iloc[0]).split(";")
         tax_lineage_rank_list = (ref_taxids_df.loc[selection_idx]['lineage_ranks'].iloc[0]).split(";")
         #print(tax_lineage_rank_list);print(tax_lineage_name_list)
         taxonony_lineages_dict_list.append(OrderedDict(zip(tax_lineage_rank_list,tax_lineage_name_list)))
    #
    ranks=['superkingdom','phylum', 'class', 'order', 'family', 'genus', 'species'] #important to have them in hierarchical order
    #create lineage statistics dictionary per rank (e.g. 'superkingdom', ['Bacteria', 'Bacteria' ...],'phylum',[...])
    #print(taxonony_lineages_dict_list)
    stats_host_range_dict=OrderedDict({rank:list() for rank in ranks})
    for lineage_record in taxonony_lineages_dict_list:
         for rank in stats_host_range_dict.keys():
             stats_host_range_dict[rank].append(lineage_record.get(rank))
    #
    #print(stats_host_range_dict)

    # missing_stats={}
    # for key in stats_host_range_dict.keys():
    #     taxa_list = stats_host_range_dict[key]
    #     #print(taxa_list)
    #     if any([i== None for i in taxa_list]):
    #         missing_stats[key]=Counter(taxa_list)[None]/len(taxa_list)
    #     else:
    #         missing_stats[key]=0
    #
    # #print("MISSING RATES PER TAXONONIC RANK:\n", missing_stats)
    #
    # #get predicted host range rank
    # convergance_rank="NA"; converged_taxonomy_name="NA"
    # bottom_up_tax_ranks_list=[i for i in reversed(stats_host_range_dict.keys())]
    # for tax_rank in bottom_up_tax_ranks_list: #rank:list(item names)
    #     value = stats_host_range_dict[tax_rank]
    #     n_unique_items = len(set(value))
    #     unique_items = list(set(value))
    #
    #     if  (any([i == None for i in stats_host_range_dict[tax_rank]]) == True and n_unique_items == 2) or \
    #         (n_unique_items == 1 and any([i != None for i in unique_items])):
    #         convergance_rank = tax_rank
    #         converged_taxonomy_name=list(set([i for i in value if i is not None]))[0] #host range is calculated here
    #         break
    #
    #
    # logging.info("HOST RANGE RESULT: {} (level) {} (rank)\n".format(converged_taxonomy_name, convergance_rank))
    #
    # #print("HOST RANGE:{} RANK LEVEL:{}\n".format(converged_taxonomy_name, convergance_rank))
    #
    # #for rank in ranks:
    # #    print("{}: {}".format(rank,dict(Counter(stats_host_range_dict[rank]))))

    return(convergance_rank, converged_taxonomy_name, unique_ref_selected_taxids, ref_taxids_df,stats_host_range_dict)



def writeOutHostRangeReports(   filename_prefix = None,
                                replicon_name_list = None,
                                mob_cluster_id = None,
                                relaxase_name_acc = None,
                                relaxase_name_list = None,
                                convergance_rank = None,
                                convergance_taxonomy = None,
                                stats_host_range_dict = None,
                                literature_hr_report = pandas.DataFrame()
                                ):


    if replicon_name_list != None:
        replicons = ",".join(replicon_name_list)
    else:
        replicons = replicon_name_list
    if relaxase_name_list  != None:
        relaxases = ",".join(relaxase_name_list )
    else:
        relaxases = relaxase_name_list

    #if no_header_flag is True: #flag to write header in the report file
    #    with open(file=filename_prefix + "_hostrange_ncbi_nucleotide_report.txt", mode="w") as fp:
    #        fp.write("{}\t{}\t{}\t{}\t{}\t{}\n".format("QueryReplicon(s)", "QueryClusterID", "QueryRelaxase(s)",
    #                                                       "QueryRelaxaseAccession", "RefSeqRank", "RefSeqHostRange"))

    #with open(file=filename_prefix+"_hostrange_ncbi_nucleotide_report.txt", mode="a") as fp:
    #        fp.write("{}\t{}\t{}\t{}\t{}\t{}\n".format(replicons, mob_cluster_id,
    #                                                       relaxases, relaxase_name_acc, convergance_rank,
    #                                                       convergance_taxonomy))
    #fp.close()
    #logging.info("Wrote RefSeq host range report results into {}".format(
    #     filename_prefix + "_hostrange_ncbi_nucleotide_report.txt"))  # replicon,relaxase,cluster,host range



    #decompose resulting phylogenetic tree into frequency counts per reach taxonomic rank (hierachy level)
    strings2file = ["rank\tsci_name\tRefSeq_db_hits\tQueryReplicon(s)\tQueryClusterID\tQueryRelaxase(s)\tQueryRelaxaseAccession\tRefSeqRank\tRefSeqHostRange\n"]
    with open(file=filename_prefix+"_ncbi_nucleotide_phylostats.txt", mode="w") as fp:
        for rank in stats_host_range_dict.keys():
            names = (Counter(stats_host_range_dict[rank]).keys())
            values = (Counter(stats_host_range_dict[rank]).values())
            for couple in zip(names,values):
               strings2file.append("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(rank,couple[0],couple[1],replicons, mob_cluster_id,
                                                           relaxases, relaxase_name_acc, convergance_rank,
                                                           convergance_taxonomy))
        fp.writelines(strings2file)
        fp.close()
        logging.info(
            "Wrote phylogeny stats into {}".format(filename_prefix + "_refseq_hostrange_tree_phylostats.txt"))

    # literature report
    if literature_hr_report.shape[0] != 0:
        literature_hr_report.to_csv(filename_prefix + '_literature_report.txt', sep="\t", index=False, na_rep="NA", mode="w")



def getTaxonomyTree(taxids):
    """
    Generate and render taxonomical tree as text or image based on the list of taxonomic ids (taxids)
    :param taxids: list of NCBI Taxonomy ids (e.g. 562 - E.coli)
    :return: tree: object of PhyloTree class from ete3 library
    """
    ncbi = NCBITaxa()

    tree = ncbi.get_topology(taxids)
    #prune tree
    #print(tree.get_ascii(attributes=["rank","name","sci_name"])) ;
    #need to prune tree as extra taxids are returned even at the species level obstructing the freq hit counts
    for node in tree.traverse():
        #print(node.rank, node.taxid)
        if any([t for t in taxids if node.taxid == t]):
            #print("Found species node")
            for c in node.get_children():
                #print("Delete child",c.sci_name,c.taxid)
                c.delete(prevent_nondicotomic=False)

        #if node.is_leaf() and any([ t for t in taxids if t == node.taxid]) == False:
        #   print("Error")
        #if node.rank == "no rank":
        #    node.delete()

    return(tree)

def loadHostRangeDB():
    database_abs_path = os.path.dirname(os.path.abspath(__file__))+"/databases/"+"host_range_plasmidDB.csv"
    #print(database_abs_path)
    data_obs_hr = pandas.read_csv(database_abs_path, sep=",", encoding="ISO-8859-1")
    return data_obs_hr


def getHostRangeDBSubset(hr_obs_data, search_name, column_name, matchtype):
    """
    From the NCBI plasmid curated database get a subset as per search query (e.g. replicon, clusterid, relaxase)
    :param hr_obs_data: host range observed data from RefSeq database NCBI
    :param search_name: a search string
    :param column_name: a search string
    :param matchtype: a sting
    :return: dataframe containing selected NCBI plasmid information (accession number, mobility, size, etc.)
    """
    #print(matchtype,column_name,search_name,hr_obs_data.loc[0:5,column_name])
    selection_index = list()
    if matchtype == "exact":
        for item in hr_obs_data[column_name]:
            if str(item) == str(search_name):
                selection_index.append(True)
            else:
                selection_index.append(False)
        return (hr_obs_data.loc[selection_index])
    elif matchtype == "multiexact":
        for item in hr_obs_data[column_name]:
            if any([i for i in str(item).split(',') if i == search_name]):
                selection_index.append(True)
            else:
                selection_index.append(False)
        return (hr_obs_data.loc[selection_index])
    elif matchtype == "loose":  # will losely match for query cases such as IncF*
        for item in hr_obs_data[column_name]:
            if len(re.findall(search_name+".*", item)) != 0:
                selection_index.append(True)
            else:
                selection_index.append(False)
        return (hr_obs_data.loc[selection_index])
    else:
        exit("No match type specified (could be either exact (--exact_match) or multi (--multi_match))")

#parse cml arguments if run as separate module
def parse_args():
    parser = ArgumentParser(description="Welcome to mob-suite plasmid host range prediction module :-)")
    parser.add_argument('--exact_match',action='store_const', const="True", required=False, help='Single exact search criteria match')
    parser.add_argument('--multi_match', action='store_const', const="True", required=False, help='Multiple exact search criteria match')
    parser.add_argument('--loose_match', action='store_const', const="True", required=False,help='Wildcard loose search criteria match (e.g. IncF* will match IncFI, IncFII, etc.)')
    parser.add_argument('--replicon_name',  action='store', nargs=1, required=False, help='Replicon name(s)')
    parser.add_argument('--relaxase_name', action='store', nargs=1, required=False, help='Relaxase name')
    parser.add_argument('--relaxase_accession', action='store', required=False, help='Relaxase accession number')
    parser.add_argument('--cluster_id', action='store', required=False, help='MOB-Suite Cluster ID (e.g. 416)')
    parser.add_argument('--host_range_detailed', required=False, help='Complete host range report with phylogeny stats',
                        action='store_true',
                        default=False)
    parser.add_argument('--outdir', action='store', required=True, help='Output files name prefix')
    parser.add_argument('--inputseq', action='store', required=False, help='Single plasmid sequence in FASTA format (optional)')
    parser.add_argument('--debug', required=False, help='Show debug detailed information (optional)', action='store_true')

    args = parser.parse_args()


    #if multiple replicons are present, then we convert them into a list
    if args.replicon_name:
        #print(args.replicon_name)
        args.replicon_name = re.split(",", args.replicon_name[0])

    #CASE1: prohibited characters in the name
    #correct file names that come with the prohibited characters like / or \ (e.g. IncA/C2)
    args.outdir = re.sub("[\\|//]+", "", args.outdir)

    #CASE2: Output file exists. Remove the old version
    #if os.path.exists(args.outdir+".txt"):
    #    os.remove(args.outdir+".txt")

    if args.debug:
        logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]", level=logging.DEBUG)
    #print(parser.parse_args())
    #print(parser.parse_args().output)
    #exit()
    return(args)

#def getHostRange_module_enty_point(replicon_name,  mob_cluster_id, relaxase_name_acc, relaxase_name):
#    global args

def main():
    """
    Main entry point into the host-range module
    :param   inputs   replicon name (e.g. IncI,ColI), MOB-suite plasmid clusterID, single plasmid sequence
    :return: reports  text-based reports on NCBI and literature reported host-range and experimentally reported plasmid range
    """
    global args
    args = parse_args()


    logging.info("Running host range main function")
    logging.info("Parsing command line arguments")


    #determine type of the NCBI reference database match
    if args.exact_match != None:
        matchtype="exact"    # single ORF replicon match
    elif args.loose_match != None:
        matchtype="loose"    # approximate ORF replicon match such as replicon family name (e.g. F)
    elif args.multi_match != None:
        matchtype="multiexact"     # multiple ORFs replicon match
    else:
        matchtype=None

    logging.info("INPUT: Replicon=" + str(args.replicon_name) + " and MOB-SuiteClusterID=" + str(args.cluster_id) + ";")
    logging.info("Started to run the main taxonomy query function per feature")

    # hostrange based on MOB-Suite  RefSeq database
    (rank, host_range, taxids, taxids_df, stats_refseq_host_range_dict) = getRefSeqHostRange(args.replicon_name, args.cluster_id,
                                                                                 args.relaxase_name,
                                                                                 args.relaxase_accession, matchtype,
                                                                                 loadHostRangeDB())

    #get literature based host range for each replicon
    lit_report, littaxids = getLiteratureBasedHostRange(args.replicon_name, loadliteratureplasmidDB())
    if args.replicon_name and lit_report.empty == False and args.host_range_detailed:
        treeRefSeq = getTaxonomyTree(taxids)  # get a phylogenetic tree
        renderTree(tree=treeRefSeq, taxids=taxids,
                   filename_prefix=args.outdir + "/mob_hostrange_" + args.outdir + "_refseqhostrange_")

        treeLiterature = getTaxonomyTree(littaxids)
        renderTree(tree=treeLiterature,taxids=littaxids,
                   filename_prefix=args.outdir+"/mob_hostrange_"+args.outdir+"_literaturehostrange_")


    writeOutHostRangeReports( filename_prefix=args.outdir+"/mob_hostrange_"+args.outdir, replicon_name_list = args.replicon_name,
                        mob_cluster_id = args.cluster_id,
                        relaxase_name_acc = args.relaxase_accession,
                        relaxase_name_list = args.relaxase_name,
                        convergance_rank = rank, convergance_taxonomy = host_range,
                        stats_host_range_dict = stats_refseq_host_range_dict,
                        literature_hr_report=lit_report)

    logging.info("Host Range module run is complete!")

def renderTree(tree,taxids,filename_prefix):
    ts = TreeStyle()
    ts.show_leaf_name = False
    ts.show_scale = False
    ts.show_branch_length = False

    # print(dir(ts))
    # print(tree.get_ascii(attributes=["sci_name"]))

    # pandas.DataFrame.to_csv(ref_taxids_df, "/Users/kirill/WORK/MOBSuiteHostRange2018/selected_df.csv")

    # prettify the rendered tree providing the stats on the tree
    # annotate nodes of the tree
    for node in tree.traverse():
        # print(node.features) #{'rank', 'common_name', 'support', 'sci_name', 'named_lineage', 'taxid', 'lineage', 'name', 'dist'}
        # print(node.sci_name)
        # print(ref_taxids_df)
        nhits = len([t for t in taxids if t == node.taxid])
        # print("{}:{}".format(node.taxid,nhits))
        node.img_style['size'] = nhits
        node.img_style['fgcolor'] = "red"
        node.img_style['hz_line_color'] = "red"
        node.img_style['vt_line_color'] = "red"
        node.img_style['draw_descendants'] = True
        # print(node.img_style)
        node.name = re.sub("_", "", node.sci_name) + "|taxid" + str(node.taxid) + "|" + str(
            nhits) + "hits"  # Newick does not like spaces in labels
        # node.name=node.sci_name
        # print(len(node.name))
        # print(node.name, node.img_style)
        # node.set_style()
        # print(node.features)
    # exit()
    # tree.show(tree_style=ts)

    # write an image
    tree.render(filename_prefix+"phylogeny_tree.png", dpi=2800, w=2000, tree_style=ts)
    with open(file=filename_prefix+ "asci_tree.txt", mode="w") as fp:
        fp.write(tree.get_ascii(attributes=["rank", "sci_name"]))
    logging.info("Wrote ASCII host range tree into {}".format(
            filename_prefix + "asci_tree.txt"))
    tree.write(format=2, outfile=filename_prefix + "phylogeny_tree.nwk")



if __name__ == "__main__":
    # setup the application logging
    main()
    logging.info("Run completed")
    #getTaxidsPerRelaxase()
    #IncI2


#TODO
# BATCH mode processing
# Add phylogenetic stats for the literature inferred tree. Need to add taxonomy lineages full path in literature database


# mob_typer run
# cp *.py /Users/kirill/miniconda/envs/mob_suite_test/lib/python3.6/site-packages/mob_suite/
# mob_typer --host_range -i /Users/kirill/WORK/MOBSuiteHostRange2018/Source/mob-suite/mob_suite/tests/TestData/IncF/ET11_Ecoli_plasmid_529.fasta -o run_test