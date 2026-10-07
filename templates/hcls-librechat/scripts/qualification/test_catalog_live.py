import pytest

from catalog_live import assistant_for_turn


def test_canonical_message_identity_not_requested_message_identity():
    intent = {'messageId': 'client-id', 'parentMessageId': 'previous-assistant'}
    user = {'messageId': 'server-id', 'parentMessageId': 'previous-assistant',
            'isCreatedByUser': True, 'text': 'list Apps'}
    assistant = {'messageId': 'answer', 'parentMessageId': 'server-id',
                 'isCreatedByUser': False}
    unrelated = {'messageId': 'unrelated', 'parentMessageId': 'another-turn',
                 'isCreatedByUser': False}
    assert assistant_for_turn([user, assistant, unrelated], intent, 'list Apps') is assistant


def test_unrelated_messages_do_not_complete_a_turn():
    assert assistant_for_turn([{'messageId': 'unrelated', 'isCreatedByUser': False}],
                              {'parentMessageId': 'parent'}, 'list Apps') is None


def test_ambiguous_same_parent_same_prompt_is_not_silently_reconciled():
    users = [{'messageId': identifier, 'parentMessageId': 'parent',
              'isCreatedByUser': True, 'text': 'list Apps'} for identifier in ('one', 'two')]
    with pytest.raises(AssertionError, match='Ambiguous'):
        assistant_for_turn(users, {'parentMessageId': 'parent'}, 'list Apps')
