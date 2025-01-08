import re
from flask import Flask, request, abort
import json
import base64

app = Flask(__name__)
MAX_MEM = '1024Mi'
MAX_CPU = '1'

@app.route('/mutate', methods=['POST'])
def mutate():
    admission_review = request.get_json()

    try:
        resource = admission_review['request']['object']
        kind = resource['kind']
        spec = resource.get('spec', {})
    except KeyError:
        abort(400, 'Invalid admission review')

    match kind:
        case 'Pod':
            mutate_pod(spec)
        case 'Deployment' | 'StatefulSet' | 'DaemonSet' | 'Job':
            template_spec = spec.get('template', {}).get('spec', {})
            mutate_pod(template_spec)
        case 'CronJob':
            template_spec = spec.get('jobTemplate', {}).get('spec', {}).get('template', {}).get('spec', {})
            mutate_cronjob(spec)
            mutate_pod(template_spec)
        case _:
            abort(400, 'Unsupported resource type')

    admission_review['response'] = {
        'uid': admission_review['request']['uid'],
        'allowed': True,
        'patchType': 'JSONPatch',
        'patch': base64.b64encode(json.dumps([
            {"op": "replace", "path": "/spec", "value": spec}
        ]).encode()).decode()
    }

    return admission_review

def mutate_pod(spec):
    containers = spec.get('containers', [])
    for container in containers:
        if not container.get('resources'):
            container['resources'] = {}
        resources = container['resources']
        resources['limits'] = {'cpu': MAX_CPU, 'memory': MAX_MEM, 'hugepages-2Mi': 0, 'hugepages-1Gi': 0}
        resources['requests'] = {'cpu': "1m", 'memory': 1, 'hugepages-2Mi': 0, 'hugepages-1Gi': 0}

def mutate_cronjob(spec):
    if spec.get('concurrencyPolicy') != 'Forbid' and spec.get('concurrencyPolicy') != 'Replace':
        spec['concurrencyPolicy'] = 'Forbid'

def main():
    app.run(host='0.0.0.0', port=4433, ssl_context=('/etc/sslcerts/cert.pem', '/etc/sslcerts/key.pem'))

if __name__ == '__main__':
    main()
