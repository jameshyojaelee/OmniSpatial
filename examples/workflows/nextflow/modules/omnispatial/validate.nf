process OMNISPATIAL_VALIDATE {
    tag "$sample_id"
    publishDir params.report_dir, mode: 'copy'

    input:
        tuple val(sample_id), path(bundle)

    output:
        tuple val(sample_id), path("${sample_id}.validation.json")

    script:
    def reportName = "${sample_id}.validation.json"
    def validationFormat = params.validation_format ?: params.format
    """
    python ${workflow.projectDir}/../scripts/run_omnispatial.py validate \
      --bundle ${bundle} \
      --format ${validationFormat} \
      --emit-json \
      > ${reportName}
    """
}
