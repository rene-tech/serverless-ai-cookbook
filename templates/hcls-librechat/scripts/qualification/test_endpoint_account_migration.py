"""Account migration changes attachment coordinates, never original message data."""
import copy

from restore_endpoint_account import migrate_files


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
