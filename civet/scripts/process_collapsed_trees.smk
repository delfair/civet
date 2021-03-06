
from Bio import Phylo
from Bio import SeqIO
import csv
import collections

config["tree_stems"] = config["catchment_str"].split(",")

rule all:
    input:
        expand(os.path.join(config["tempdir"], "collapsed_trees","{tree}.tree"), tree = config["tree_stems"]),
        os.path.join(config["outdir"],"local_trees","collapse_report.txt"),
        expand(os.path.join(config["outdir"],"local_trees","{tree}.tree"), tree = config["tree_stems"])

rule get_basal_representative:
    input:
        tree = os.path.join(config["tempdir"], "catchment_trees","{tree}.newick")
    output:
        basal = os.path.join(config["tempdir"],"representatives","{tree}.txt")
    shell:
        """
        clusterfunk return_basal \
        -i {input.tree} --in-format newick \
        -o {output.basal}
        """

rule get_basal_seq:
    input:
        basal = rules.get_basal_representative.output.basal,
        fasta  = config["cog_global_seqs"]
    params:
        tree = "{tree}"
    output:
        fasta = os.path.join(config["tempdir"], "representatives","{tree}.fasta")
    run:
        basal_taxon = ""
        with open(input.basal, "r") as f:
            for l in f:
                l = l.rstrip("\n")
                basal_taxon = l
        with open(output.fasta, "w") as fw:
            for record in SeqIO.parse(input.fasta, "fasta"):
                if record.id == basal_taxon:
                    node_name = "_".join(params.tree.split("_")[1:])
                    fw.write(f">{node_name} representative={record.id}\n{record.seq}\n")

rule combine_basal:
    input:
        expand(os.path.join(config["tempdir"], "representatives","{tree}.fasta"), tree=config["tree_stems"])
    output:
        fasta = os.path.join(config["tempdir"], "all_basal_seqs.fasta")
    shell:
        "cat {input} > {output:q}"

rule protect_subtree_nodes:
    input:
        metadata = config["combined_metadata"]
    params:
        tree_dir = os.path.join(config["tempdir"],"catchment_trees")
    output:
        metadata = os.path.join(config["tempdir"],"protected","protected.csv")
    run:
        with open(output.metadata, "w") as fw:
            fw.write("protect,count\n")
            c =0
            for r,d,f in os.walk(params.tree_dir):
                for fn in f:
                    if fn.endswith(".newick"):
                        tree = ".".join(fn.split(".")[:-1])
                        node_name = "_".join(tree.split("_")[1:])
                        c +=1
                        fw.write(f"{node_name},{c}\n")
            
            with open(input.metadata, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c+=1
                    fw.write(row["closest"] + f",{c}\n")
        

rule summarise_polytomies:
    input:
        metadata = os.path.join(config["tempdir"],"protected","protected.csv"),
        tree = os.path.join(config["tempdir"], "catchment_trees","{tree}.newick")
    params:
        tree_dir = os.path.join(config["tempdir"],"catchment_trees"),
        threshold = config["threshold"]
    output:
        collapsed_tree = os.path.join(config["tempdir"],"collapsed_trees","{tree}.tree"),
        collapsed_information = os.path.join(config["outdir"],"local_trees","{tree}.txt")
    shell:
        """
        clusterfunk focus -i {input.tree:q} \
        -o {output.collapsed_tree:q} \
        --metadata {input.metadata:q} \
        --index-column protect \
        --in-format newick \
        --out-format newick \
        --threshold {params.threshold} \
        --output-tsv {output.collapsed_information:q}
        """

rule get_collapsed_representative:
    input:
        cog_seqs = config["cog_global_seqs"],
        collapsed_information = rules.summarise_polytomies.output.collapsed_information
    params:
        tree_dir = os.path.join(config["tempdir"],"collapsed_trees")
    output:
        representative_seq = os.path.join(config["tempdir"],"collapsed_trees","{tree}_representatives.fasta"),
    run:
        collapsed = {}
        collapsed_seqs = collections.defaultdict(list)
        
        with open(input.collapsed_information, "r") as f:
            for l in f:
                l = l.rstrip("\n")
                collapsed_name,taxa = l.split('\t')
                collapsed[collapsed_name] = taxa.split(",")
        for record in SeqIO.parse(input.cog_seqs,"fasta"):
            for node in collapsed:
                if record.id in collapsed[node]:
                    collapsed_seqs[node].append(record)

        with open(output.representative_seq, "w") as fw:
            for node in collapsed_seqs:
                records = collapsed_seqs[node]
                sorted_with_amb = []
                for record in records:
                    amb_count = 0
                    for base in record.seq:
                        if base.upper() not in ["A","T","C","G","-"]:
                            amb_count +=1
                    amb_pcent = (100*amb_count) / len(record.seq)
                    sorted_with_amb.append((record.id, amb_pcent, record.seq))
                sorted_with_amb = sorted(sorted_with_amb, key = lambda x : x[1])
                rep = sorted_with_amb[0]
                fw.write(f">{node} representative={rep[0]} ambiguity={rep[1]}\n{rep[2]}\n")
        
rule extract_taxa:
    input:
        collapsed_tree = os.path.join(config["tempdir"],"collapsed_trees","{tree}.tree")
    output:
        tree_taxa = os.path.join(config["tempdir"], "collapsed_trees","{tree}_taxon_names.txt")
    shell:
        "clusterfunk get_taxa -i {input.collapsed_tree:q} --in-format newick -o {output.tree_taxa:q} --out-format newick"

rule gather_fasta_seqs:
    input:
        collapsed_nodes = os.path.join(config["tempdir"],"collapsed_trees","{tree}_representatives.fasta"),
        aligned_query_seqs = config["aligned_query_seqs"],
        cog_seqs = config["all_cog_seqs"],
        outgroup_fasta = config["outgroup_fasta"],
        combined_metadata = config["combined_metadata"],
        tree_taxa = rules.extract_taxa.output.tree_taxa,
        all_basal_seqs = os.path.join(config["tempdir"], "all_basal_seqs.fasta")
    output:
        aln = os.path.join(config["tempdir"], "catchment_aln","{tree}.query.aln.fasta")
    run:
        taxa = []
        with open(input.tree_taxa, "r") as f:
            for l in f:
                l = l.rstrip("\n")
                taxa.append(l)

        queries = {}
        with open(input.combined_metadata,newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["closest"] in taxa:
                    if row["closest"] != row["query"]:
                        queries[row["query"]] = row["query_id"]

        added_seqs = []
        with open(output.aln, "w") as fw:
            for record in SeqIO.parse(input.outgroup_fasta, "fasta"):
                fw.write(f">{record.description}\n{record.seq}\n")
                added_seqs.append(record.id)

            for record in SeqIO.parse(input.aligned_query_seqs, "fasta"):
                if record.id in queries.values() or record.id in queries.keys():
                    fw.write(f">{record.description}\n{record.seq}\n")
                    added_seqs.append(record.id)

            for record in SeqIO.parse(input.collapsed_nodes, "fasta"):
                fw.write(f">{record.description}\n{record.seq}\n")
                added_seqs.append(record.id)

            for record in SeqIO.parse(input.cog_seqs,"fasta"):
                if record.id in taxa:
                    fw.write(f">{record.description}\n{record.seq}\n")
                    added_seqs.append(record.id)

            for record in SeqIO.parse(input.all_basal_seqs,"fasta"):
                if record.id in taxa:
                    fw.write(f">{record.description}\n{record.seq}\n")
                    added_seqs.append(record.id)

rule hash_for_iqtree:
    input:
        aln = rules.gather_fasta_seqs.output.aln
    output:
        hash = os.path.join(config["tempdir"], "renamed_trees","{tree}.hash_for_iqtree.csv"),
        hashed_aln = os.path.join(config["tempdir"], "renamed_trees","{tree}.query.aln.fasta")
    run:
        fw = open(output.hash, "w")
        fw.write("taxon,iqtree_hash,cluster_hash\n")
        hash_count = 0
        with open(output.hashed_aln, "w") as fseq:
            for record in SeqIO.parse(input.aln, "fasta"):
                hash_count +=1
                if record.id == "outgroup":
                    fw.write(f"outgroup,outgroup,outgroup\n")
                    fseq.write(f">outgroup\n{record.seq}\n")
                else:
                    without_str = record.id.rstrip("'").lstrip("'")
                    fw.write(f"{without_str},_taxon_{hash_count}_,taxon_{hash_count}\n")
                    fseq.write(f">'taxon_{hash_count}'\n{record.seq}\n")
        fw.close()

rule hash_tax_labels:
    input:
        tree=os.path.join(config["tempdir"],"collapsed_trees","{tree}.tree"),
        hash = rules.hash_for_iqtree.output.hash
    output:
        tree = os.path.join(config["tempdir"],"renamed_trees","{tree}.tree")
    shell:
        """
        clusterfunk relabel_tips -i {input.tree:q} \
        -o {output[0]:q} \
        --in-metadata {input.hash:q} \
        --index-column taxon \
        --trait-columns cluster_hash \
        --replace \
        --in-format newick \
        --out-format newick
        """

rule iqtree_catchment:
    input:
        aln = os.path.join(config["tempdir"], "renamed_trees","{tree}.query.aln.fasta")
    output:
        tree = os.path.join(config["tempdir"], "renamed_trees","{tree}.query.aln.fasta.treefile")
    shell:
        "iqtree -s {input.aln:q} -au -m HKY -nt 1 -redo -o outgroup"


rule restore_tip_names:
    input:
        tree = rules.iqtree_catchment.output.tree,
        hash = rules.hash_for_iqtree.output.hash
    output:
        os.path.join(config["tempdir"],"almost_restored_trees","{tree}.tree")
    shell:
        """
        clusterfunk relabel_tips -i {input.tree:q} \
        -o {output[0]:q} \
        --in-metadata {input.hash:q} \
        --index-column iqtree_hash \
        --trait-columns taxon \
        --replace \
        --in-format newick \
        --out-format newick
        """

rule prune_outgroup:
    input:
        tree = os.path.join(config["tempdir"],"almost_restored_trees","{tree}.tree"),
        prune = config["outgroup_fasta"]
    output:
        tree = os.path.join(config["tempdir"],"outgroup_pruned","{tree}.tree")
    shell:
        """
        clusterfunk prune -i {input.tree:q} \
        -o {output.tree:q} \
        --fasta {input.prune:q} \
        --in-format newick \
        --out-format newick
        """

rule remove_str_for_baltic:
    input:
        tree = os.path.join(config["tempdir"],"outgroup_pruned","{tree}.tree")
    output:
        tree = os.path.join(config["tempdir"],"outgroup_pruned","{tree}.newick")
    run:
        with open(output.tree,"w") as fw:
            with open(input.tree, "r") as f:
                for l in f:
                    l = l.rstrip("\n")
                    l = l.replace("'","")
                    fw.write(l)

rule to_nexus:
    input:
        tree = os.path.join(config["tempdir"],"outgroup_pruned","{tree}.newick")
    output:
        tree = os.path.join(config["outdir"],"local_trees","{tree}.tree")
    run:
        Phylo.convert(input[0], 'newick', output[0], 'nexus')

rule summarise_processing:
    input:
        collapse_reports = expand(os.path.join(config["outdir"],"local_trees","{tree}.txt"), tree=config["tree_stems"])
    output:
        report = os.path.join(config["outdir"],"local_trees","collapse_report.txt")
    run:
        with open(output.report, "w") as fw:
            for report in input.collapse_reports:
                fn = os.path.basename(report)
                with open(report, "r") as f:
                    for l in f:
                        l = l.rstrip("\n")
                        new_l = f"{fn}\t{l}\n"
                        fw.write(new_l)
