import importlib.util
import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

spec = importlib.util.spec_from_file_location('deploy_link', Path(__file__).with_name('deploy-link.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_launch_form_has_persistent_state_but_no_customer_identity_or_secret():
    image = 'example.invalid/client@sha256:' + 'a' * 64
    url = urlsplit(module.deployment_link(image))
    assert url.scheme == 'https' and url.netloc == 'console.nebius.com'
    values = parse_qs(url.query)
    assert values == {'image': [image], 'targetPort': ['3080'], 'platform': ['cpu-d3'],
                      'preset': ['4vcpu-16gb'], 'diskSize': ['100GiB'], 'preemptible': ['false'],
                      'volumeMountPath': ['/data'], 'volumeSize': ['32']}


@pytest.mark.parametrize('image', ['example/client:latest', 'https://key@example/client', 'client?token=private'])
def test_unpinned_or_credential_urls_are_not_launch_images(image):
    with pytest.raises(ValueError):
        module.deployment_link(image)


def test_release_has_a_valid_launch_link():
    assert '@sha256:' in module.release_image()
    assert module.deployment_link(module.release_image()).startswith('https://console.nebius.com/')


def test_readme_button_tracks_the_same_immutable_release():
    readme = Path(__file__).resolve().parents[1] / 'README.md'
    link = re.search(r'<a href="(https://console\.nebius\.com/serverless/endpoint/create\?[^\"]+)"',
                     readme.read_text())
    assert link is not None
    assert html.unescape(link.group(1)) == module.deployment_link(module.release_image())
