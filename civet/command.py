#!/usr/bin/env python3
from civet import __version__
import setuptools
import argparse
import os.path
import snakemake
import sys
from tempfile import gettempdir
import tempfile
import pprint
import json
import csv
import os
from datetime import datetime
from Bio import SeqIO

import pkg_resources
from . import _program

"""
Need query_csv, metadata, fasta (opt)
"""


thisdir = os.path.abspath(os.path.dirname(__file__))
cwd = os.getcwd()

def main(sysargs = sys.argv[1:]):

    parser = argparse.ArgumentParser(prog = _program, 
    description='civet: Cluster Investivation & Virus Epidemiology Tool', 
    usage='''civet <query> [options]''')

    parser.add_argument('query',help="Input csv file with minimally `name` as a column header. Can include additional fields to be incorporated into the analysis, e.g. `sample_date`",)
    parser.add_argument('-i',"--id-string", action="store_true",help="Indicates the input is a comma-separated id string with one or more query ids. Example: `EDB3588,EDB3589`.", dest="ids")
    parser.add_argument('-f','--fasta', action="store",help="Optional fasta query.", dest="fasta")
    parser.add_argument('-sc',"--sequencing-centre", action="store",help="Customise report with logos from sequencing centre.", dest="sequencing_centre")
    parser.add_argument('--CLIMB', action="store_true",dest="climb",help="Indicates you're running CIVET from within CLIMB, uses default paths in CLIMB to access data")
    parser.add_argument('--cog-report', action="store_true",help="Run summary cog report. Default: outbreak investigation",dest="cog_report")
    parser.add_argument("-r",'--remote-sync', action="store_true",dest="remote",help="Remotely access lineage trees from CLIMB")
    parser.add_argument("-uun","--your-user-name", action="store", help="Your CLIMB COG-UK username. Required if running with --remote-sync flag", dest="uun")
    parser.add_argument('-o','--outdir', action="store",help="Output directory. Default: current working directory")
    parser.add_argument('-b','--launch-browser', action="store_true",help="Optionally launch md viewer in the browser using grip",dest="launch_browser")
    parser.add_argument('-d','--datadir', action="store",help="Local directory that contains the data files")
    parser.add_argument('--fields', action="store",help="Comma separated string of fields to display in the trees in the report. Default: country")
    parser.add_argument('--display', action="store", help="Comma separated string of fields to display as coloured dots rather than text in report trees. Optionally add colour scheme eg adm1=viridis", dest="display")
    parser.add_argument('--label-fields', action="store", help="Comma separated string of fields to add to tree report labels.", dest="label_fields")
    parser.add_argument("--node-summary", action="store", help="Column to summarise collapsed nodes by. Default = Global lineage", dest="node_summary")
    parser.add_argument('--search-field', action="store",help="Option to search COG database for a different id type. Default: COG-UK ID", dest="search_field",default="central_sample_id")
    parser.add_argument('--distance', action="store",help="Extraction from large tree radius. Default: 2", dest="distance",default=2)
    parser.add_argument('--up-distance', action="store",help="Upstream distance to extract from large tree. Default: 2", dest="up_distance",default=2)
    parser.add_argument('--down-distance', action="store",help="Downstream distance to extract from large tree. Default: 2", dest="down_distance",default=2)
    parser.add_argument('--add-boxplots', action="store_true",help="Render boxplots in the output report", dest="add_boxplots")
    # parser.add_argument('--delay-tree-collapse',action="store_true",dest="delay_tree_collapse",help="Wait until after iqtree runs to collapse the polytomies. NOTE: This may result in large trees that take quite a while to run.")
    parser.add_argument('-g','--global',action="store_true",dest="search_global",help="Search globally.")
    parser.add_argument('-n', '--dry-run', action='store_true',help="Go through the motions but don't actually run")
    parser.add_argument('--tempdir',action="store",help="Specify where you want the temp stuff to go. Default: $TMPDIR")
    parser.add_argument("--no-temp",action="store_true",help="Output all intermediate files, for dev purposes.")
    parser.add_argument('--collapse-threshold', action='store',type=int,help="Minimum number of nodes to collapse on. Default: 1", dest="threshold", default=1)
    parser.add_argument('-t', '--threads', action='store',type=int,help="Number of threads")
    parser.add_argument("--verbose",action="store_true",help="Print lots of stuff to screen")
    parser.add_argument('--max-ambig', action="store", default=0.5, type=float,help="Maximum proportion of Ns allowed to attempt analysis. Default: 0.5",dest="maxambig")
    parser.add_argument('--min-length', action="store", default=10000, type=int,help="Minimum query length allowed to attempt analysis. Default: 10000",dest="minlen")
    parser.add_argument('--local-lineages',action="store_true",dest="local_lineages",help="Contextualise the cluster lineages at local regional scale. Requires at least one adm2 value in query csv.", default=False)
    parser.add_argument('--date-restriction',action="store_true",dest="date_restriction",help="Chose whether to date-restrict comparative sequences at regional-scale.", default=False)
    parser.add_argument('--date-range-start',action="store",default="None", type=str, dest="date_range_start", help="Define the start date from which sequences will COG sequences will be used for local context. YYYY-MM-DD format required.")
    parser.add_argument('--date-range-end', action="store", default="None", type=str, dest="date_range_end", help="Define the end date from which sequences will COG sequences will be used for local context. YYYY-MM-DD format required.")
    parser.add_argument('--date-window',action="store",default=7, type=int, dest="date_window",help="Define the window +- either side of cluster sample collection date-range. Default is 7 days.")
    parser.add_argument("-v","--version", action='version', version=f"civet {__version__}")

    parser.add_argument("--map-sequences", action="store_true", dest="map_sequences", help="Map the coordinate points of sequences, coloured by a triat.")
    parser.add_argument("--x-col", required=False, dest="x_col", help="column containing x coordinate for mapping sequences")
    parser.add_argument("--y-col", required=False, dest="y_col", help="column containing y coordinate for mapping sequences")
    parser.add_argument("--input-crs", required=False, dest="input_crs", help="Coordinate reference system of sequence coordinates")
    parser.add_argument("--mapping-trait", required=False, dest="mapping_trait", help="Column to colour mapped sequences by")

    acceptable_colours = ['viridis', 'plasma', 'inferno', 'magma', 'cividis','Greys', 
            'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
            'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
            'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn',
            'binary', 'gist_yarg', 'gist_gray', 'gray', 'bone', 'pink',
            'spring', 'summer', 'autumn', 'winter', 'cool', 'Wistia',
            'hot', 'afmhot', 'gist_heat', 'copper',
            'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
            'RdYlBu', 'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic',
            'twilight', 'twilight_shifted', 'hsv',
            'Pastel1', 'Pastel2', 'Paired', 'Accent',
            'Dark2', 'Set1', 'Set2', 'Set3',
            'tab10', 'tab20', 'tab20b', 'tab20c',
            'flag', 'prism', 'ocean', 'gist_earth', 'terrain', 'gist_stern',
            'gnuplot', 'gnuplot2', 'CMRmap', 'cubehelix', 'brg',
            'gist_rainbow', 'rainbow', 'jet', 'nipy_spectral', 'gist_ncar']

    # Exit with help menu if no args supplied
    if len(sysargs)<1: 
        parser.print_help()
        sys.exit(-1)
    else:
        args = parser.parse_args(sysargs)

    # find the master Snakefile
    snakefile = os.path.join(thisdir, 'scripts','Snakefile')
    if not os.path.exists(snakefile):
        sys.stderr.write('Error: cannot find Snakefile at {}\n Check installation'.format(snakefile))
        sys.exit(-1)
    
    # find the query fasta
    if args.fasta:
        fasta = os.path.join(cwd, args.fasta)
        if not os.path.exists(fasta):
            sys.stderr.write('Error: cannot find fasta query at {}\n'.format(fasta))
            sys.exit(-1)
        else:
            print(f"Input fasta file: {fasta}")
    else:
        fasta = ""

    # default output dir
    outdir = ''
    if args.outdir:
        rel_outdir = args.outdir #for report weaving
        outdir = os.path.join(cwd, args.outdir)
        figdir = os.path.join(outdir, "figures")
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        if not os.path.exists(figdir):
            os.mkdir(figdir)
            
    else:
        timestamp = str(datetime.now().isoformat(timespec='milliseconds')).replace(":","").replace(".","").replace("T","-")
        outdir = os.path.join(cwd, timestamp)
        figdir = os.path.join(outdir, "figures")
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        if not os.path.exists(figdir):
            os.mkdir(figdir)
        
        rel_outdir = os.path.join(".",timestamp)
    
    print(f"Output files will be written to {outdir}\n")

    # specifying temp directory
    tempdir = ''
    if args.tempdir:
        to_be_dir = os.path.join(cwd, args.tempdir)
        if not os.path.exists(to_be_dir):
            os.mkdir(to_be_dir)
        temporary_directory = tempfile.TemporaryDirectory(suffix=None, prefix=None, dir=to_be_dir)
        tempdir = temporary_directory.name
    else:
        temporary_directory = tempfile.TemporaryDirectory(suffix=None, prefix=None, dir=None)
        tempdir = temporary_directory.name

    # if no temp, just write everything to outdir
    if args.no_temp:
        print(f"--no-temp: All intermediate files will be written to {outdir}")
        tempdir = outdir

    # find the query csv, or string of ids
    query = os.path.join(cwd, args.query)
    if not os.path.exists(query):
        if args.ids:
            id_list = args.query.split(",")
            query = os.path.join(tempdir, "query.csv")
            with open(query,"w") as fw:
                fw.write("name\n")
                for i in id_list:
                    fw.write(i+'\n')
        else:
            sys.stderr.write(f"Error: cannot find query file at {query}\n Check if the file exists, or if you're inputting an id string (e.g. EDB3588,EDB2533), please use in conjunction with the `--id-string` flag\n.")
            sys.exit(-1)
    else:
        print(f"Input file: {query}")


    # parse the input csv, check col headers and get fields if fields specified
    fields = []
    labels = []
    queries = []
    graphics_list = []

    with open(query, newline="") as f:
        reader = csv.DictReader(f)
        column_names = reader.fieldnames
        if "name" not in column_names:
            sys.stderr.write(f"Error: Input file missing header field `name`\n.")
            sys.exit(-1)

        if not args.fields:
            fields.append("adm1")
            print("No fields to colour by provided, will colour by adm1 by default.\n")
        else:
            desired_fields = args.fields.split(",")
            for field in desired_fields:
                if field in reader.fieldnames:
                    fields.append(field)
                else:
                    sys.stderr.write(f"Error: {field} field not found in metadata file")
                    sys.exit(-1)

        
        if not args.label_fields:
            labels.append("NONE")
        else:
            label_fields = args.label_fields.split(",")
            for label_f in label_fields:
                if label_f in reader.fieldnames:
                    labels.append(label_f)
                else:
                    sys.stderr.write(f"Error: {label_f} field not found in metadata file")
                    sys.exit(-1)

        if args.display:
            sections = args.display.split(",")
            for item in sections:
                splits = item.split("=")
                graphic_trait = splits[0]
                if graphic_trait in reader.fieldnames:
                    if len(splits) == 1:
                        graphics_list.append(graphic_trait + ":default")
                    else:
                        colour_scheme = splits[1]
                        if colour_scheme in acceptable_colours:
                            graphics_list.append(graphic_trait + ":" + colour_scheme)
                        else:
                            sys.stderr.write(f"Error: {colour_scheme} not a matplotlib compatible colour scheme s")
                            sys.stderr.write(f"Please use one of {acceptable_colours}")
                            sys.exit(-1)
                else:
                    sys.stderr.write(f"Error: {graphic_trait} field not found in metadata file")
                    sys.exit(-1)
        else:
            graphics_list.append("adm1:default")
        
        print("COG-UK ids to process:")
        for row in reader:
            queries.append(row["name"])
            
            print(row["name"])
        print(f"Total: {len(queries)}")
    print('\n')
    # how many threads to pass
    if args.threads:
        threads = args.threads
    else:
        threads = 1
    print(f"Number of threads: {threads}\n")

    # create the config dict to pass through to the snakemake file
    config = {
        "query":query,
        "fields":",".join(fields),
        "label_fields":",".join(labels),
        "outdir":outdir,
        "tempdir":tempdir,
        "trim_start":265,   # where to pad to using datafunk
        "trim_end":29674,   # where to pad after using datafunk
        "fasta":fasta,
        "rel_outdir":rel_outdir,
        "search_field":args.search_field,
        "force":"True",
        "date_range_start":args.date_range_start,
        "date_range_end":args.date_range_end,
        "date_window":args.date_window,
        "graphic_dict":",".join(graphics_list)
        }

    if args.add_boxplots:
        config["add_boxplots"]= True
    else:
        config["add_boxplots"]= False
        
    if args.map_sequences:
        config["map_sequences"] = True
        if not args.x_col or not args.y_col:
            sys.stderr.write('Error: coordinates not supplied for mapping sequences. Please provide --x-col and --y-col')
            sys.exit(-1)
        elif not args.input_crs:
            sys.stderr.write('Error: input coordinate system not provided for mapping. Please provide --input-crs eg EPSG:3395')
            sys.exit(-1)
        else:
            config["x_col"] = args.x_col
            config["y_col"] = args.y_col
            config["input_crs"] = args.input_crs

        with open(query, newline="") as f:
            reader = csv.DictReader(f)
            column_names = reader.fieldnames
            relevant_cols = [args.x_col, args.y_col, args.mapping_trait]
            for map_arg in relevant_cols:

                if map_arg and map_arg not in reader.fieldnames:
                    sys.stderr.write(f"Error: {map_arg} field not found in metadata file")
                    sys.exit(-1)

        if args.mapping_trait:
            config["mapping_trait"] = args.mapping_trait
        else:
            config["mapping_trait"] = False
            
    else:
        config["map_sequences"] = False
        config["x_col"] = False
        config["y_col"] = False
        config["input_crs"] = False
        config["mapping_trait"] = False

    if args.local_lineages:
        config['local_lineages'] = "True"
        with open(query, newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            if not "adm2" in header:
                sys.stderr.write(f"Error: --local-lineages argument called, but input csv file doesn't have an adm2 column. Please provide that to have local lineage analysis.\n")
                sys.exit(-1)
    else:
        config['local_lineages'] = "False"

    if args.date_restriction:
        config['date_restriction'] = "True"
    else:
        config['date_restriction'] = "False"

    """ 
    QC steps:
    1) check csv header
    2) check fasta file N content
    3) write a file that contains just the seqs to run
    """
    # find the data files
    data_dir = ""
    if args.climb or args.datadir:
        if args.climb:
            data_dir = "/cephfs/covid/bham/civet-cat"
            if os.path.exists(data_dir):
                config["remote"] = "False"
                config["username"] = ""
            else:
                sys.stderr.write(f"Error: --CLIMB argument called, but CLIMB data path doesn't exist.\n")
                sys.exit(-1)

        elif args.datadir:
            data_dir = os.path.join(cwd, args.datadir)
        if not args.remote:
            cog_metadata,all_cog_metadata,cog_global_metadata = ("","","")
            cog_seqs,all_cog_seqs = ("","")
            cog_tree = ""
            
            cog_seqs = os.path.join(data_dir,"cog_alignment.fasta")
            all_cog_seqs = os.path.join(data_dir,"cog_alignment_all.fasta")
            
            cog_metadata = os.path.join(data_dir,"cog_metadata.csv")
            all_cog_metadata = os.path.join(data_dir,"cog_metadata_all.csv")

            cog_global_metadata = os.path.join(data_dir,"cog_global_metadata.csv")
            cog_global_seqs= os.path.join(data_dir,"cog_global_alignment.fasta")

            cog_tree = os.path.join(data_dir,"cog_global_tree.nexus")

            if not os.path.isfile(cog_seqs) or not os.path.isfile(cog_global_seqs) or not os.path.isfile(all_cog_seqs) or not os.path.isfile(cog_metadata) or not  os.path.isfile(all_cog_metadata) or not os.path.isfile(cog_global_metadata) or not os.path.isfile(cog_tree):
                sys.stderr.write(f"""Error: cannot find correct data files at {data_dir}\nThe directory should contain the following files:\n\
        - cog_global_tree.nexus\n\
        - cog_alignment_all.fasta\n\
        - cog_metadata.csv\n\
        - cog_metadata_all.csv\n\
        - cog_global_metadata.csv\n\
        - cog_global_alignment.fasta\n\
        - cog_alignment.fasta\n\n\
    To run civet please either\n1) ssh into CLIMB and run with --CLIMB flag\n\
    2) Run using `--remote-sync` flag and your CLIMB username specified e.g. `-uun climb-covid19-otoolexyz`\n\
    3) Specify a local directory with the appropriate files\n\n""")
                sys.exit(-1)
            else:
                config["cog_seqs"] = cog_seqs
                config["all_cog_seqs"] = all_cog_seqs

                config["cog_metadata"] = cog_metadata
                config["all_cog_metadata"] = all_cog_metadata
                config["cog_global_metadata"] = cog_global_metadata
                config["cog_global_seqs"] = cog_global_seqs
                config["cog_tree"] = cog_tree

                print("Found cog data:")
                print("    -",cog_seqs)
                print("    -",all_cog_seqs)
                print("    -",cog_metadata)
                print("    -",all_cog_metadata)
                print("    -",cog_global_metadata)
                print("    -",cog_tree,"\n")

    else:
        print("No data directory specified, will save data in civet-cat in current working directory")
        data_dir = cwd


    # if remote flag, and uun provided, sync data from climb
    if args.remote:
        config["remote"]= "True"
        if args.uun:
            config["username"] = args.uun
        
            rsync_command = f"rsync -avzh {args.uun}@bham.covid19.climb.ac.uk:/cephfs/covid/bham/civet-cat '{data_dir}'"
            print(f"Syncing civet data to {data_dir}")
            status = os.system(rsync_command)
            if status != 0:
                sys.stderr.write("Error: rsync command failed.\nCheck your user name is a valid CLIMB username e.g. climb-covid19-smithj\nAlso, check if you have access to CLIMB from this machine and are in the UK\n\n")
                sys.exit(-1)
        else:
            rsync_command = f"rsync -avzh bham.covid19.climb.ac.uk:/cephfs/covid/bham/civet-cat '{data_dir}'"
            print(f"Syncing civet data to {data_dir}")
            status = os.system(rsync_command)
            if status != 0:
                sys.stderr.write("Error: rsync command failed.\nCheck your ssh is configured with Host bham.covid19.climb.ac.uk\nAlternatively enter your CLIMB username with -uun e.g. climb-covid19-smithj\nAlso, check if you have access to CLIMB from this machine and are in the UK\n\n")
                sys.exit(-1)
        cog_metadata,all_cog_metadata,cog_global_metadata = ("","","")
        cog_seqs,all_cog_seqs = ("","")
        cog_tree = ""

        cog_seqs = os.path.join(data_dir,"civet-cat","cog_alignment.fasta")
        all_cog_seqs = os.path.join(data_dir,"civet-cat","cog_alignment_all.fasta")

        cog_metadata = os.path.join(data_dir,"civet-cat","cog_metadata.csv")
        all_cog_metadata = os.path.join(data_dir,"civet-cat","cog_metadata_all.csv")

        cog_global_metadata = os.path.join(data_dir,"civet-cat","cog_global_metadata.csv")
        cog_global_seqs= os.path.join(data_dir,"civet-cat","cog_global_alignment.fasta")

        cog_tree = os.path.join(data_dir,"civet-cat","cog_global_tree.nexus")

        config["cog_seqs"] = cog_seqs
        config["all_cog_seqs"] = all_cog_seqs

        config["cog_metadata"] = cog_metadata
        config["all_cog_metadata"] = all_cog_metadata
        config["cog_global_metadata"] = cog_global_metadata
        config["cog_global_seqs"] = cog_global_seqs
        config["cog_tree"] = cog_tree

        print("Found cog data:")
        print("    -",cog_seqs)
        print("    -",all_cog_seqs)
        print("    -",cog_metadata)
        print("    -",all_cog_metadata)
        print("    -",cog_global_metadata)
        print("    -",cog_tree,"\n")

    elif not args.datadir and not args.climb:
        sys.stderr.write("""Error: no way to find source data.\n\nTo run civet please either\n1) ssh into CLIMB and run with --CLIMB flag\n\
2) Run using `--remote-sync` flag and your CLIMB username specified e.g. `-uun climb-covid19-otoolexyz`\n\
3) Specify a local directory with the appropriate files on. The following files are required:\n\
- cog_global_tree.nexus\n\
- cog_metadata.csv\n\
- cog_metadata_all.csv\n\
- cog_global_metadata.csv\n\
- cog_global_alignment.fasta\n\
- cog_alignment.fasta\n\n""")
        sys.exit(-1)

    # run qc on the input sequence file
    if args.fasta:
        do_not_run = []
        run = []
        for record in SeqIO.parse(args.fasta, "fasta"):
            if len(record) <args.minlen:
                record.description = record.description + f" fail=seq_len:{len(record)}"
                do_not_run.append(record)
                print(f"    - {record.id}\tsequence too short: Sequence length {len(record)}")
            else:
                num_N = str(record.seq).upper().count("N")
                prop_N = round((num_N)/len(record.seq), 2)
                if prop_N > args.maxambig: 
                    record.description = record.description + f" fail=N_content:{prop_N}"
                    do_not_run.append(record)
                    print(f"    - {record.id}\thas an N content of {prop_N}")
                else:
                    run.append(record)

        post_qc_query = os.path.join(outdir, 'query.post_qc.fasta')
        with open(post_qc_query,"w") as fw:
            SeqIO.write(run, fw, "fasta")
        qc_fail = os.path.join(outdir,'query.failed_qc.csv')
        with open(qc_fail,"w") as fw:
            fw.write("name,reason_for_failure\n")
            for record in do_not_run:
                desc = record.description.split(" ")
                for i in desc:
                    if i.startswith("fail="):
                        fw.write(f"{record.id},{i}\n")

        config["post_qc_query"] = post_qc_query
        config["qc_fail"] = qc_fail
    else:
        config["post_qc_query"] = ""
        config["qc_fail"] = ""

    if args.search_global:
        config["global"]="True"
    else:
        config["global"]="False"

    # delay tree colapse
    # if args.delay_tree_collapse:
    #     print("--delay-tree-collapse: Warning tree building may take a long time.")
    #     config["delay_collapse"] = "True"
    # else:
    config["delay_collapse"] = "False"

    # accessing package data and adding to config dict
    reference_fasta = pkg_resources.resource_filename('civet', 'data/reference.fasta')
    outgroup_fasta = pkg_resources.resource_filename('civet', 'data/outgroup.fasta')
    polytomy_figure = pkg_resources.resource_filename('civet', 'data/polytomies.png')
    footer_fig = pkg_resources.resource_filename('civet', 'data/footer.png')
    clean_locs = pkg_resources.resource_filename('civet', 'data/mapping_files/adm2_cleaning.csv')
    map_input_1 = pkg_resources.resource_filename('civet', 'data/mapping_files/gadm36_GBR_2.json')
    map_input_2 = pkg_resources.resource_filename('civet', 'data/mapping_files/channel_islands.json')  
    map_input_3 = pkg_resources.resource_filename('civet', 'data/mapping_files/NI_counties.geojson')  
    map_input_4 = pkg_resources.resource_filename('civet', 'data/mapping_files/Mainland_HBs_gapclosed_mapshaped_d3.json')
    map_input_5 = pkg_resources.resource_filename('civet', 'data/mapping_files/urban_areas_UK.geojson')
    spatial_translations_1 = pkg_resources.resource_filename('civet', 'data/mapping_files/HB_Translation.pkl')
    spatial_translations_2 = pkg_resources.resource_filename('civet', 'data/mapping_files/adm2_regions_to_coords.csv')

    if args.cog_report:
        report_template = os.path.join(thisdir, 'scripts','COG_template.pmd')
    else:
        report_template = os.path.join(thisdir, 'scripts','civet_template.pmd')
    
    if not os.path.exists(report_template):
        sys.stderr.write('Error: cannot find report_template at {}\n'.format(report_template))
        sys.exit(-1)

    with open(cog_global_metadata, newline="") as f:
        reader = csv.DictReader(f)
        column_names = reader.fieldnames

        if not args.node_summary:
                summary = "country"
        else:
            if args.node_summary in column_names:
                summary = args.node_summary
            else:
                sys.stderr.write(f"Error: {args.node_summary} field not found in metadata file\n")
                sys.exit(-1)
        
        print(f"Going to summarise collapsed nodes by: {summary}")
        config["node_summary"] = summary

    config["reference_fasta"] = reference_fasta
    config["outgroup_fasta"] = outgroup_fasta
    config["polytomy_figure"] = polytomy_figure
    config["footer"] = footer_fig
    config["report_template"] = report_template
    config["clean_locs"] = clean_locs
    config["uk_map"] = map_input_1
    config["channels_map"] = map_input_2
    config["ni_map"] = map_input_3
    config["uk_map_d3"] = map_input_4
    config["urban_centres"] = map_input_5
    config["HB_translations"] = spatial_translations_1
    config["PC_translations"] = spatial_translations_2

    sc_list = ["PHEC", 'LIVE', 'BIRM', 'PHWC', 'CAMB', 'NORW', 'GLAS', 'EDIN', 'SHEF',
                 'EXET', 'NOTT', 'PORT', 'OXON', 'NORT', 'NIRE', 'GSTT', 'LOND', 'SANG',"NIRE"]

    if args.sequencing_centre:
        if args.sequencing_centre in sc_list:
            relative_file = os.path.join("data","headers",f"{args.sequencing_centre}.png")
            header = pkg_resources.resource_filename('civet', relative_file)
            print(f"using header file from {header}\n")
            config["sequencing_centre"] = header
        else:
            sc_string = "\n".join(sc_list)
            sys.stderr.write(f'Error: sequencing centre must be one of the following:\n{sc_string}\n')
            sys.exit(-1)
    else:
        relative_file = os.path.join("data","headers","DEFAULT.png")
        header = pkg_resources.resource_filename('civet', relative_file)
        print(f"using header file from {header}\n")
        config["sequencing_centre"] = header

    if args.distance:
        try:
            distance = int(args.distance) 
            config["up_distance"] = args.distance
            config["down_distance"] = args.distance
        except:
            sys.stderr.write('Error: distance must be an integer\n')
            sys.exit(-1)
    else:
        config["up_distance"] = "1"
        config["down_distance"] = "1"

    if args.up_distance:
        try:
            distance = int(args.up_distance) 
            config["up_distance"] = args.up_distance
        except:
            sys.stderr.write('Error: up-distance must be an integer\n')
            sys.exit(-1)

    if args.down_distance:
        try:
            distance = int(args.down_distance) 
            config["down_distance"] = args.down_distance
        except:
            sys.stderr.write('Error: down-distance must be an integer\n')
            sys.exit(-1)


    if args.threshold:
        try:
            threshold = int(args.threshold)
            config["threshold"] = args.threshold
        except:
            sys.stderr.write('Error: threshold must be an integer\n')
            sys.exit(-1)
    else:
        config["threshold"] = "1"

    if args.launch_browser:
        config["launch_browser"]="True"

    # don't run in quiet mode if verbose specified
    if args.verbose:
        quiet_mode = False
        config["quiet_mode"]="False"
    else:
        quiet_mode = True
        config["quiet_mode"]="True"

    status = snakemake.snakemake(snakefile, printshellcmds=True,
                                 dryrun=args.dry_run, forceall=True,force_incomplete=True,workdir=tempdir,
                                 config=config, cores=threads,lock=False,quiet=quiet_mode
                                 )

    if status: # translate "success" into shell exit code of 0
       return 0

    return 1

if __name__ == '__main__':
    main()