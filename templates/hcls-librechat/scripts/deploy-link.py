#!/usr/bin/env python3
"""Print a secret-free Serverless console link for the selected client release.

This opens a prefilled form, not an authenticated zero-input deployment. Registry
access, project, secret selectors and the workspace mount still belong to the
customer. The separate 32 GiB /data filesystem preserves the chat database.
"""
import argparse
from pathlib import Path
import re
from urllib.parse import urlencode


def release_image():
    values = dict(re.findall(r"^(SCIENTIFIC_AI_RELEASE_(?:IMAGE|DIGEST))='([^']+)'$",
                            Path(__file__).with_name('release-image.sh').read_text(), re.M))
    image = values['SCIENTIFIC_AI_RELEASE_IMAGE'].rsplit(':', 1)[0]
    return image + '@' + values['SCIENTIFIC_AI_RELEASE_DIGEST']


def deployment_link(image):
    if not re.fullmatch(r'[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}', image):
        raise ValueError('The launch image must have a pinned sha256 digest, not credentials or a moving tag')
    return 'https://console.nebius.com/serverless/endpoint/create?' + urlencode({
        'image': image, 'targetPort': '3080', 'platform': 'cpu-d3', 'preset': '4vcpu-16gb',
        'diskSize': '100GiB', 'preemptible': 'false', 'volumeMountPath': '/data', 'volumeSize': '32',
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Explicit candidate digest; default is the shared release')
    args = parser.parse_args()
    print(deployment_link(args.image or release_image()))
