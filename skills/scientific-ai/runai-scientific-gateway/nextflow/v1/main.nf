nextflow.enable.types = true
include { SCIENTIFIC_AI_STAGE_V1 } from './scientific_ai_stage_v1'
params {
    request: Path
    service_url: String
    submission_key: String
}
workflow {
    stage = SCIENTIFIC_AI_STAGE_V1(params.request, file("${projectDir}/client.py"), params.service_url, params.submission_key)
    stage.run_id.view { path -> "Scientific AI run: ${path.text.trim()}" }
    stage.manifest.view { path -> "Verified manifest: ${path.name}" }
    stage.scientific_outputs.view { path -> "Scientific outputs: ${path.name}" }
}
