"""Account migration changes attachment coordinates, never original message data."""
import copy

from restore_endpoint_account import image_metadata, migrate_files, message_signature
from uuid import UUID
import pytest


def test_native_image_contract_includes_archived_dimensions():
    metadata = image_metadata({'original': {'width': 512, 'height': 256}})
    assert metadata['endpoint'] == 'agents'
    assert metadata['width'] == '512' and metadata['height'] == '256'
    assert UUID(metadata['file_id'])


def test_invalid_image_dimensions_are_not_guessed():
    with pytest.raises(ValueError):
        image_metadata({'original': {'width': 0, 'height': 256}})


def test_only_transient_assistant_renderer_handles_are_normalized():
    old = {'text': '', 'isCreatedByUser': False,
           'content': [{'type': 'text', 'text': 'The result: \\ui{c9e982c43b}'}]}
    new = copy.deepcopy(old)
    new['content'][0]['text'] = 'The result: '
    assert message_signature(old) == message_signature(new)
    old['isCreatedByUser'] = new['isCreatedByUser'] = True
    assert message_signature(old) != message_signature(new)
    old['isCreatedByUser'] = new['isCreatedByUser'] = False
    new['content'][0]['text'] = 'Different scientific result'
    assert message_signature(old) != message_signature(new)


def test_image_references_are_mapped_without_mutating_archive():
    messages = [{'text': 'Compare these cells', 'isCreatedByUser': True,
                 'content': [{'type': 'text', 'text': 'Original text'}],
                 'files': [{'file_id': 'old', 'filepath': '/images/old.png', 'width': 512}]}]
    original = copy.deepcopy(messages)
    mapped = migrate_files(messages, {'old': {'file_id': 'new', 'filepath': '/images/new.png'}})
    assert messages == original
    assert mapped[0]['content'] == original[0]['content']
    assert mapped[0]['text'] == original[0]['text']
    assert mapped[0]['files'] == [{'file_id': 'new', 'filepath': '/images/new.png', 'width': 512}]


def test_messages_without_files_and_unknown_references_are_unchanged():
    messages = [{'text': 'No attachment'}, {'text': '', 'files': [{'file_id': 'unmapped'}]}]
    assert migrate_files(messages, {}) == messages
