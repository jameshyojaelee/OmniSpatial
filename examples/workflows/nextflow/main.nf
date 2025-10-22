nextflow.enable.dsl = 2

include { OMNISPATIAL_CONVERT as convert } from './modules/omnispatial/convert'
include { OMNISPATIAL_VALIDATE as validate } from './modules/omnispatial/validate'

workflow {
    if (!(params.samples instanceof Map) || params.samples.isEmpty()) {
        log.warn "No samples supplied. Configure 'params.samples' as a map of sample IDs to input paths."
        return
    }

    Channel
        .from(params.samples)
        .map { sample_id, sample_path -> tuple(sample_id as String, file(sample_path)) }
        .map { sample_id, dataset ->
            def bundleSuffix = params.format == 'spatialdata' ? 'sdata.zarr' : 'ngff.zarr'
            def bundleName = "${sample_id}.${bundleSuffix}"
            def args = []
            if (params.vendor) args << "--vendor ${params.vendor}"
            if (params.image_chunks) args << "--image-chunks ${params.image_chunks}"
            if (params.label_chunks) args << "--label-chunks ${params.label_chunks}"
            tuple(sample_id, dataset, bundleName, args.join(' '))
        }
        .set { convert_input }

    converted = convert(convert_input)

    if (params.validate) {
        validate(converted.out)
    }
}
