import csv
from Bio import SeqIO
import os
import collections

rule check_cog_db:
    input:
        query = config["query"],
        cog_seqs = config["cog_seqs"],
        cog_metadata = config["cog_metadata"]
    params:
        field_to_match = config["search_field"]
    output:
        cog = os.path.join(config["tempdir"],"query_in_cog.csv"),
        cog_seqs = os.path.join(config["tempdir"],"query_in_cog.fasta"),
        not_cog = os.path.join(config["tempdir"],"not_in_cog.csv")
    shell:
        """
        check_cog_db.py --query {input.query:q} \
                        --cog-seqs {input.cog_seqs:q} \
                        --cog-metadata {input.cog_metadata:q} \
                        --field {params.field_to_match} \
                        --in-metadata {output.cog:q} \
                        --in-seqs {output.cog_seqs:q} \
                        --not-in-cog {output.not_cog:q}
        """
        
rule check_cog_all:
    input:
        not_in_cog = rules.check_cog_db.output.not_cog,
        cog_seqs = config["all_cog_seqs"],
        cog_metadata = config["all_cog_metadata"]
    params:
        field_to_match = config["search_field"]
    output:
        cog = os.path.join(config["tempdir"],"query_in_all_cog.csv"),
        cog_seqs = os.path.join(config["tempdir"],"query_in_all_cog.fasta"),
        not_cog = os.path.join(config["tempdir"],"not_in_all_cog.csv")
    shell:
        """
        check_cog_db.py --query {input.not_in_cog:q} \
                        --cog-seqs {input.cog_seqs:q} \
                        --cog-metadata {input.cog_metadata:q} \
                        --field {params.field_to_match} \
                        --in-metadata {output.cog:q} \
                        --in-seqs {output.cog_seqs:q} \
                        --not-in-cog {output.not_cog:q} \
                        --all-cog
        """

rule get_closest_cog:
    input:
        snakefile = os.path.join(workflow.current_basedir,"find_closest_cog.smk"),
        reference_fasta = config["reference_fasta"],
        cog_seqs = config["cog_seqs"],
        cog_metadata = config["cog_metadata"],
        seq_db = config["seq_db"],
        not_cog_csv = rules.check_cog_all.output.not_cog, #use
        in_all_cog_metadata = rules.check_cog_all.output.cog,
        in_all_cog_seqs = rules.check_cog_all.output.cog_seqs #use 
    params:
        outdir= config["outdir"],
        tempdir= config["tempdir"],
        path = workflow.current_basedir,
        cores = workflow.cores,
        force = config["force"],
        fasta = config["fasta"], #use
        search_field = config["search_field"],
        qc_fail_csv = config["qc_fail"],
        query = config["post_qc_query"], #use
        stand_in_query = os.path.join(config["tempdir"], "temp.fasta"),
        trim_start = config["trim_start"],
        trim_end = config["trim_end"],
        quiet_mode = config["quiet_mode"]
    output:
        closest_cog = os.path.join(config["tempdir"],"closest_cog.csv"),
        combined_query = os.path.join(config["tempdir"],"to_find_closest.fasta"),
        aligned_query = os.path.join(config["tempdir"],"post_qc_query.aligned.fasta"),
        not_processed = os.path.join(config["tempdir"], "no_seq_to_process.csv")
    run:
        query_with_no_seq = []
        to_find_closest = {}

        for record in SeqIO.parse(input.in_all_cog_seqs,"fasta"):
            to_find_closest[record.id] = ("COG_database",record.seq)

        not_cog = []
        with open(input.not_cog_csv, newline = "") as f: # getting list of non-cog queries
            reader = csv.DictReader(f)
            for row in reader:
                not_cog.append(row["name"])
        
        failed_qc = []
        if params.qc_fail_csv != "":
            with open(params.qc_fail_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    failed_qc.append(row["name"])

        if params.fasta != "":
             # get set with supplied sequences
                print("Not in COG but have a sequence supplied:")
                for record in SeqIO.parse(params.query, "fasta"):
                    if record.id in not_cog:
                        to_find_closest[record.id] = ("fasta",record.seq) # overwrites with supplied seq if found in all cog

        with open(output.combined_query, "w") as fw:
            for seq in to_find_closest:
                fw.write(f">{seq} status={to_find_closest[seq][0]}\n{to_find_closest[seq][1]}\n")

        for query in not_cog: # get set with no sequences supplied
            if query not in to_find_closest and query not in failed_qc:
                query_with_no_seq.append(query)

        if len(list(set(query_with_no_seq))) != 0:
            print("The following seqs were not found in COG and a fasta file was not provided, so CIVET was unable to add them into phylogenies:")
        with open(output.not_processed, "w") as fw:
            for query in list(set(query_with_no_seq)):
                fw.write(f"{query},fail=no sequence provided\n")
                print(f"{query}")

        if to_find_closest != {}:
            print(f"Passing {len(to_find_closest)} sequences into nearest COG search pipeline:")
            for seq in to_find_closest:
                print(f"    - {seq}    {to_find_closest[seq][0]}")
            shell("snakemake --nolock --snakefile {input.snakefile:q} "
                        "{params.force} "
                        "{params.quiet_mode} "
                        "--directory {params.tempdir:q} "
                        "--config "
                        "tempdir={params.tempdir:q} "
                        "seq_db={input.seq_db:q} "
                        "to_find_closest={output.combined_query:q} "
                        "search_field={params.search_field} "
                        "trim_start={params.trim_start} "
                        "trim_end={params.trim_end} "
                        "reference_fasta={input.reference_fasta:q} "
                        "cog_metadata={input.cog_metadata:q} "
                        "--cores {params.cores}")

        else:
            shell("touch {output.closest_cog:q} && touch {output.aligned_query:q}")


rule combine_metadata:
    input:
        closest_cog = rules.get_closest_cog.output.closest_cog,
        in_cog = rules.check_cog_db.output.cog
    output:
        combined_csv = os.path.join(config["outdir"],"combined_metadata.csv")
    run:
        with open(input.in_cog, newline="") as f:
            reader = csv.DictReader(f)
            header_names = reader.fieldnames
            with open(output.combined_csv, "w") as fw:
                header_names.append("closest_distance")
                header_names.append("snps")
                writer = csv.DictWriter(fw, fieldnames=header_names,lineterminator='\n')
                writer.writeheader()
            
                for row in reader:
                    
                    new_row = row
                    new_row["closest_distance"]="0"
                    new_row["snps"]= ""

                    writer.writerow(new_row)

                with open(input.closest_cog, newline="") as fc:
                    readerc = csv.DictReader(fc)
                    for row in readerc:
                        writer.writerow(row)

rule prune_out_catchments:
    input:
        tree = config["cog_tree"],
        metadata = rules.combine_metadata.output.combined_csv
    params:
        outdir = os.path.join(config["tempdir"],"catchment_trees"),
        up_distance = config["up_distance"],
        down_distance = config["down_distance"]
    output:
        txt = os.path.join(config["tempdir"],"catchment_trees","catchment_trees_prompt.txt")
    shell:
        """
        jclusterfunk context \
        -i {input.tree:q} \
        -o {params.outdir:q} \
        --max-parent {params.up_distance} \
        --max-child {params.down_distance} \
        -f newick \
        -p tree_ \
        --ignore-missing \
        -m {input.metadata:q} \
        --id-column closest \
        && touch {output.txt:q} 
        """

rule process_catchments:
    input:
        snakefile_collapse_after = os.path.join(workflow.current_basedir,"process_catchment_trees.smk"), #alternative snakefiles
        snakefile_collapse_before = os.path.join(workflow.current_basedir,"process_collapsed_trees.smk"),
        snakefile_just_collapse = os.path.join(workflow.current_basedir,"just_collapse_trees.smk"),
        combined_metadata = rules.combine_metadata.output.combined_csv, 
        query_seqs = rules.get_closest_cog.output.aligned_query, #datafunk-processed seqs
        catchment_prompt = rules.prune_out_catchments.output.txt,
        all_cog_seqs = config["all_cog_seqs"],
        outgroup_fasta = config["outgroup_fasta"],
        cog_global_seqs = config["cog_global_seqs"]
        # not_cog_csv = rules.check_cog_all.output.not_cog
    params:
        outdir= config["outdir"],
        tempdir= config["tempdir"],
        path = workflow.current_basedir,
        threshold = config["threshold"],
        delay_collapse = config["delay_collapse"],
        
        fasta = config["fasta"],
        tree_dir = os.path.join(config["tempdir"],"catchment_trees"),

        cores = workflow.cores,
        force = config["force"],
        quiet_mode = config["quiet_mode"]
    output:
        tree_summary = os.path.join(config["outdir"],"local_trees","collapse_report.txt")
    run:
        catchment_trees = []
        for r,d,f in os.walk(params.tree_dir):
            for fn in f:
                if fn.endswith(".newick"):
                    file_stem = ".".join(fn.split(".")[:-1])
                    catchment_trees.append(file_stem)
        catchment_str = ",".join(catchment_trees) #to pass to snakemake pipeline

        query_seqs = 0
        for record in SeqIO.parse(input.query_seqs,"fasta"):
            query_seqs +=1

        if query_seqs !=0:
            if params.delay_collapse==False:
                snakefile = input.snakefile_collapse_before
            else:
                snakefile = input.snakefile_collapse_after

            snakestring = f"'{snakefile}' "
            print(f"Passing {input.query_seqs} into processing pipeline.")
            shell(f"snakemake --nolock --snakefile {snakestring}"
                        "{params.force} "
                        "{params.quiet_mode} "
                        "--directory {params.tempdir:q} "
                        "--config "
                        f"catchment_str={catchment_str} "
                        "outdir={params.outdir:q} "
                        "tempdir={params.tempdir:q} "
                        "outgroup_fasta={input.outgroup_fasta:q} "
                        "aligned_query_seqs={input.query_seqs:q} "
                        "all_cog_seqs={input.all_cog_seqs:q} "
                        "cog_global_seqs={input.cog_global_seqs:q} "
                        "combined_metadata={input.combined_metadata:q} "
                        "threshold={params.threshold} "
                        "--cores {params.cores}")
        else:
            print(f"No new sequences to add in, just collapsing trees.")
            shell("snakemake --nolock --snakefile {input.snakefile_just_collapse:q} "
                            "{params.force} "
                            "{params.quiet_mode} "
                            "--directory {params.tempdir:q} "
                            "--config "
                            f"catchment_str={catchment_str} "
                            "outdir={params.outdir:q} "
                            "tempdir={params.tempdir:q} "
                            "combined_metadata={input.combined_metadata:q} "
                            "--cores {params.cores}")

rule find_snps:
    input:
        tree_summary = os.path.join(config["outdir"],"local_trees","collapse_report.txt"),
        snakefile = os.path.join(workflow.current_basedir,"find_snps.smk"),
        query_seqs = rules.get_closest_cog.output.aligned_query, #datafunk-processed seqs
        all_cog_seqs = config["all_cog_seqs"],
        outgroup_fasta = config["outgroup_fasta"]
    params:
        outdir= config["outdir"],
        tempdir= config["tempdir"],
        path = workflow.current_basedir,
        threshold = config["threshold"],
        
        fasta = config["fasta"],
        tree_dir = os.path.join(config["outdir"],"local_trees"),

        cores = workflow.cores,
        force = config["force"],
        quiet_mode = config["quiet_mode"]
    output:
        genome_graph = os.path.join(config["outdir"],"figures","genome_graph.png"),
        report = os.path.join(config["outdir"],"snp_reports","snp_reports.txt")
    run:
        local_trees = []
        for r,d,f in os.walk(params.tree_dir):
            for fn in f:
                if fn.endswith(".tree"):
                    file_stem = ".".join(fn.split(".")[:-1])
                    local_trees.append(file_stem)
        local_str = ",".join(local_trees) #to pass to snakemake pipeline

        shell("snakemake --nolock --snakefile {input.snakefile:q} "
                            "{params.force} "
                            "{params.quiet_mode} "
                            "--directory {params.tempdir:q} "
                            "--config "
                            f"catchment_str={local_str} "
                            "outdir={params.outdir:q} "
                            "tempdir={params.tempdir:q} "
                            "outgroup_fasta={input.outgroup_fasta:q} "
                            "aligned_query_seqs={input.query_seqs:q} "
                            "all_cog_seqs={input.all_cog_seqs:q} "
                            "threshold={params.threshold} "
                            "--cores {params.cores}")

rule regional_mapping:
    input:
        query = config['query'],
        combined_metadata = os.path.join(config["outdir"],"combined_metadata.csv"),
        cog_global_metadata = config["cog_global_metadata"]
    params:
        mapfile = config["uk_map_d3"],
        hb_trans = config["HB_translations"],
        local_lineages = config["local_lineages"],
        daterestrict = config["date_restriction"],
        datestart = config["date_range_start"],
        dateend = config["date_range_end"],
        datewindow = config["date_window"],
        outdir = config["rel_outdir"],
        tempdir = config['tempdir'],
        figdir = os.path.join(config["outdir"],'figures')
    output:
        central = os.path.join(config["tempdir"], "central_map_ukLin.vl.json"),
        neighboring = os.path.join(config["tempdir"], "neighboring_map_ukLin.vl.json"),
        region = os.path.join(config["tempdir"], "region_map_ukLin.vl.json")
    run:
        if params.local_lineages == "True":
            shell("""
        local_scale_analysis.py \
        --uk-map {params.mapfile:q} \
        --hb-translation {params.hb_trans:q} \
        --date-restriction {params.daterestrict:q} \
        --date-pair-start {params.datestart:q} \
        --date-pair-end {params.dateend:q} \
        --date-window {params.datewindow:q} \
        --cog-meta-global {input.cog_global_metadata:q} \
        --user-sample-data {input.query:q} \
        --output-base-dir {params.figdir:q} \
        --output-temp-dir {params.tempdir:q}
            """)
        else:
            shell("touch {output.central:q}")
            shell("touch {output.neighboring:q}")
            shell("touch {output.region:q}")

rule regional_map_rendering:
    input:
        central = os.path.join(config["tempdir"], "central_map_ukLin.vl.json"),
        neighboring = os.path.join(config["tempdir"], "neighboring_map_ukLin.vl.json"),
        region = os.path.join(config["tempdir"], "region_map_ukLin.vl.json")
    params:
        outdir = config["rel_outdir"],
        local_lineages = config["local_lineages"],
        central = os.path.join(config["tempdir"], "central_map_ukLin.vg.json"),
        neighboring = os.path.join(config["tempdir"], "neighboring_map_ukLin.vg.json"),
        region = os.path.join(config["tempdir"], "region_map_ukLin.vg.json")
    output:
        central = os.path.join(config["outdir"], 'figures', "central_map_ukLin.png"),
        neighboring = os.path.join(config["outdir"], 'figures', "neighboring_map_ukLin.png"),
        region = os.path.join(config["outdir"], 'figures', "region_map_ukLin.png")
    run:
        if params.local_lineages == "True":
            shell(
            """
            npx -p vega-lite vl2vg {input.central} {params.central}
            npx -p vega-cli vg2png {params.central} {output.central}
            """)
            shell(
            """
            npx -p vega-lite vl2vg {input.neighboring} {params.neighboring}
            npx -p vega-cli vg2png {params.neighboring} {output.neighboring}
            """)
            shell(
            """
            npx -p vega-lite vl2vg {input.region} {params.region}
            npx -p vega-cli vg2png {params.region} {output.region}
            """)
        else:
            shell("touch {output.central}")
            shell("touch {output.neighboring}")
            shell("touch {output.region}")



rule make_report:
    input:
        lineage_trees = rules.process_catchments.output.tree_summary,
        query = config["query"],
        combined_metadata = os.path.join(config["outdir"],"combined_metadata.csv"),
        cog_global_metadata = config["cog_global_metadata"],
        report_template = config["report_template"],
        polytomy_figure = config["polytomy_figure"],
        footer = config["footer"],
        clean_locs = config["clean_locs"],
        uk_map = config["uk_map"],
        channels_map = config["channels_map"],
        ni_map = config["ni_map"],
        urban_centres = config["urban_centres"],
        genome_graph = rules.find_snps.output.genome_graph,
        snp_report = rules.find_snps.output.report,
        central = os.path.join(config["outdir"], 'figures', "central_map_ukLin.png"),
        neighboring = os.path.join(config["outdir"], 'figures', "neighboring_map_ukLin.png"),
        region = os.path.join(config["outdir"], 'figures', "region_map_ukLin.png")
    params:
        treedir = os.path.join(config["outdir"],"local_trees"),
        outdir = config["rel_outdir"],
        fields = config["fields"],
        label_fields = config["label_fields"],
        node_summary = config["node_summary"],
        sc_source = config["sequencing_centre"],
        sc = config["sequencing_centre_file"],
        sc_flag = config["sequencing_centre_flag"],
        rel_figdir = os.path.join(".","figures"),
        local_lineages = config["local_lineages"],
        figdir = os.path.join(config["outdir"],"figures"),
        failure = config["qc_fail_report"],
        map_sequences = config["map_sequences"],
        x_col = config["x_col"],
        y_col = config["y_col"],
        input_crs = config["input_crs"],
        mapping_trait = config["mapping_trait"],
        add_boxplots = config["add_boxplots"],
        graphic_dict = config["graphic_dict"]
    output:
        poly_fig = os.path.join(config["outdir"],"figures","polytomies.png"),
        footer_fig = os.path.join(config["outdir"], "figures", "footer.png"),
        outfile = os.path.join(config["outdir"], "civet_report.md")
    run:
        if params.sc != "":
            shell("cp {params.sc_source:q} {params.sc:q}")
        if params.local_lineages == "True":
            lineage_tables = []
            for r,d,f in os.walk(os.path.join(config["outdir"], 'figures')):
                for fn in f:
                    if fn.endswith("_lineageTable.md"):
                        lineage_tables.append(os.path.join(config["outdir"], 'figures', fn))
            lineage_maps = [input.central, input.neighboring, input.region]

            lineage_table_string = ";".join(lineage_tables)
            lineage_map_string = ";".join(lineage_maps)

            local_lineage_flag = "--local-lineages "
            lineage_map_flag = f"--local-lin-maps '{lineage_map_string}' "
            lineage_table_flag = f"--local-lin-tables '{lineage_table_string}' "
        else:
            local_lineage_flag = ""
            lineage_map_flag = ""
            lineage_table_flag = ""
        boxplots = ""
        if config["add_boxplots"]:
            boxplots = "--add-boxplots"
        shell("""
        cp {input.polytomy_figure:q} {output.poly_fig:q} &&
        cp {input.footer:q} {output.footer_fig:q}""")
        shell(
        "make_report.py "
        "--input-csv {input.query:q} "
        "-f {params.fields:q} "
        "--graphic_dict {params.graphic_dict:q} "
        "--label-fields {params.label_fields:q} "
        "--node-summary {params.node_summary} "
        "--figdir {params.rel_figdir:q} "
        "{params.sc_flag} "
        "{params.failure} "
        "--treedir {params.treedir:q} "
        "--report-template {input.report_template:q} "
        "--filtered-cog-metadata {input.combined_metadata:q} "
        "--cog-metadata {input.cog_global_metadata:q} "
        "--clean-locs {input.clean_locs:q} "
        "--uk-map {input.uk_map:q} "
        "--channels-map {input.channels_map:q} "
        "--ni-map {input.ni_map:q} "
        "--outfile {output.outfile:q} "
        "--outdir {params.outdir:q} "
        "--map-sequences {params.map_sequences} "
        "--snp-report {input.snp_report:q} "
        "--x-col {params.x_col} "
        "--y-col {params.y_col} "
        "--input-crs {params.input_crs} "
        "--mapping-trait {params.mapping_trait} "
        "--urban-centres {input.urban_centres} "
        f"{boxplots}"
        f"{local_lineage_flag} {lineage_map_flag} {lineage_table_flag}")

rule launch_grip:
    input:
        mdfile = os.path.join(config["outdir"], "civet_report.md")
    output:
        out_file = os.path.join(config["outdir"],"civet_report.html")
    run:
        shell("grip {input.mdfile:q} --export")
        for i in range(8000, 8100):
            try:
                shell("grip {input.mdfile:q} -b {i}")
                break
            except:
                print("Trying next port")