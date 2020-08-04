#!/usr/bin/env python3
import os
from pweave import weave
import argparse
import shutil


thisdir = os.path.abspath(os.path.dirname(__file__))

def make_report(cog_metadata, input_csv, filtered_cog_metadata, outfile, outdir, treedir, figdir, colour_fields, label_fields, report_template, failed_seqs, no_seq, seq_centre, clean_locs, uk_map, channels_map, ni_map, local_lineages, local_lin_maps, local_lin_tables,map_sequences,x_col,y_col, input_crs,mapping_trait,urban_centres):

    name_stem = ".".join(outfile.split(".")[:-1])
                        
    with open(outfile, 'w') as pmd_file:
    
        md_template = report_template
        summary_dir = os.path.join(outdir, "summary_files")

        change_line_dict = {
                            "output_directory": f'output_directory = "{outdir}"\n',
                            "name_stem_input": f'name_stem_input = "{name_stem}"\n',
                            "full_metadata_file": f'full_metadata_file = "{cog_metadata}"\n',
                            "filtered_cog_metadata": f'filtered_cog_metadata = "{filtered_cog_metadata}"\n',
                            "input_csv": f'input_csv = "{input_csv}"\n',
                            "input_directory": f'input_directory = "{treedir}"\n',
                            "desired_fields_input": f'desired_fields_input = "{colour_fields}"\n',
                            "label_fields_input": f'label_fields_input = "{label_fields}"\n',
                            "figdir": f'figdir = "{figdir}"\n',
                            "tree_dir": f'tree_dir = "{treedir}"\n',
                            "summary_dir": f'summary_dir = "{summary_dir}"\n',
                            "QC_fail_file": f'QC_fail_file = "{failed_seqs}"\n',
                            "missing_seq_file": f'missing_seq_file = "{no_seq}"\n',
                            "sequencing_centre": f'sequencing_centre = "{seq_centre}"\n',
                            "clean_locs_file": f'clean_locs_file = "{clean_locs}"\n',
                            "uk_map": f'uk_map = "{uk_map}"\n',
                            "channels_map": f'channels_map = "{channels_map}"\n',
                            "ni_map": f'ni_map = "{ni_map}"\n',
                            "local_lineages":f'local_lineages = "{local_lineages}"\n',
                            "local_lin_maps" : f'local_lin_maps = "{local_lin_maps}"\n',
                            "local_lin_tables" : f'local_lin_tables = "{local_lin_tables}"\n',
                            "map_sequences":f'map_sequences = "{map_sequences}"\n', 
                            "x_col":f'x_col = "{x_col}"\n',
                            "y_col":f'y_col = "{y_col}"\n',
                            "mapping_trait":f'mapping_trait = "{mapping_trait}"\n',
                            "input_crs":f'input_crs = "{input_crs}"\n',
                            "urban_centres":f'urban_centres = "{urban_centres}"\n'
                            }
        with open(md_template) as f:
            for l in f:
                if "##CHANGE" in l:
                    for key in change_line_dict:
                        if key in l:
                            new_l = change_line_dict[key]
                else:
                    new_l = l

                pmd_file.write(new_l)
    
    weave(outfile, doctype = "pandoc", figdir=figdir)

def main():
    parser = argparse.ArgumentParser(description="Report generator script")
    parser.add_argument("-i","--input-csv", required=False, help="path to input file",dest="input_csv")
    parser.add_argument("-f", "--fields",default="", help="desired fields for report. Default=date and UK country",dest="colour_fields")
    parser.add_argument("-l", "--label-fields", default="", help="fields to add into labels in report trees. Default is adm2 and date", dest='label_fields')

    parser.add_argument("-sc", "--sequencing-centre",default="", help="Sequencing centre", dest="sc")

    parser.add_argument("--filtered-cog-metadata", required=False, help="path to combined metadata file",dest="filtered_cog_metadata")
    parser.add_argument("--cog-metadata", required=True, help="path to full COG metadata file",dest="cog_metadata")
    
    parser.add_argument("--failed-seqs", required=False, default="", help="csv of seqs that fail qc and the reason why",dest="failed_seqs")
    parser.add_argument("--no-seq-provided", required=False, default="", help="file of seqs that weren't in cog and didn't have a sequence provided",dest="no_seq")
    
    parser.add_argument("-t","--treedir", required=False, default="", help="path to tree directory",dest="treedir")
    parser.add_argument("--report-template", help="report template file",dest="report_template")

    parser.add_argument("-o","--outfile", default="civet_report.pmd", help="output name stem as a string",dest="outfile")
    parser.add_argument("--outdir", help="output directory",dest="outdir")
    parser.add_argument("--figdir", help="output directory",dest="figdir")

    parser.add_argument("--clean-locs", required=True, help="CSV for cleaning adm2 regions in metadata", dest="clean_locs")
    parser.add_argument("--uk-map", required=True, help="shape file for uk counties", dest="uk_map")
    parser.add_argument("--channels-map", required=True, help="shape file for channel islands", dest="channels_map")
    parser.add_argument("--ni-map", required=True, help="shape file for northern irish counties", dest="ni_map")

    parser.add_argument("--map-sequences", required=True, help="Bool for whether mapping of sequences by trait is required", dest="map_sequences")
    parser.add_argument("--x-col", default="", help="column name in input csv which contains x coords for mapping", dest="x_col")
    parser.add_argument("--y-col", default="", help="column name in input csv which contains y coords for mapping", dest="y_col")
    parser.add_argument("--input-crs", default="", help="coordinate reference system that x and y inputs are in", dest="input_crs")
    parser.add_argument("--mapping-trait", default="", help="trait to map sequences by", dest="mapping_trait")
    parser.add_argument("--urban-centres", default="", help="geojson for plotting urban centres", dest="urban_centres")

    parser.add_argument("--local-lineages", default="", action='store_true',help="List of rendered .png files for local lineage analysis", dest="local_lineages")
    parser.add_argument("--local-lin-maps", default="", action='store',help="List of rendered .png files for local lineage analysis", dest="local_lin_maps")
    parser.add_argument("--local-lin-tables", default="", action='store', help="List of .md tables for local lineage analysis", dest="local_lin_tables")

    args = parser.parse_args()

    make_report(args.cog_metadata, args.input_csv, args.filtered_cog_metadata, args.outfile, args.outdir, args.treedir, args.figdir,args.colour_fields, args.label_fields, args.report_template, args.failed_seqs,args.no_seq, args.sc, args.clean_locs, args.uk_map, args.channels_map, args.ni_map, args.local_lineages, args.local_lin_maps, args.local_lin_tables,args.map_sequences, args.x_col, args.y_col, args.input_crs, args.mapping_trait, args.urban_centres)


if __name__ == "__main__":
    main()