process OMNISPATIAL_CONVERT {
    tag "$sample_id"
    publishDir params.outdir, mode: 'copy'

    input:
        tuple val(sample_id), path(dataset), val(bundle_name), val(extra_args)

    output:
        tuple val(sample_id), path(bundle_name)

    script:
    def optionalArgs = extra_args?.trim() ? " ${extra_args.trim()}" : ""
    """
    python ${workflow.projectDir}/../scripts/run_omnispatial.py convert \
      --input ${dataset} \
      --output ${bundle_name} \
      --format ${params.format}${optionalArgs}
    """
}
