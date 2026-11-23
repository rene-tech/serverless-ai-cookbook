nextflow.enable.types = true

process SCIENTIFIC_AI_STAGE_V1 {
    cache 'deep'
    errorStrategy { task.exitStatus == 75 ? 'retry' : 'terminate' }
    maxRetries 2

    input:
    request_json: Path
    client: Path
    service_url: String
    submission_key: String

    stage:
    stageAs request_json, 'request.json'
    stageAs client, 'sciai_client.py'
    env 'SCIENTIFIC_AI_URL', service_url
    env 'SCIENTIFIC_AI_SUBMISSION_KEY', submission_key

    output:
    run_id: Path = file('sciai-run-id.txt')
    manifest: Path = file('verified-manifest.json')
    scientific_outputs: Path = file('outputs', type: 'dir')

    script:
    '''
    python3 sciai_client.py run request.json
    '''
}
