import uuid


def create_hash():
    return uuid.uuid4().hex

def add_metadata(msg, *, conversation_id=None, in_replay_to=None):
    msg.set_metadata("language", "json")
    msg.set_metadata("ontology", "seroid")
    msg.set_metadata("protocol", "fipa-query")
    if conversation_id is None:  # means first msg in chain
        msg.set_metadata("conversation-id", create_hash())
    else:
        msg.set_metadata("conversation-id", conversation_id)
    msg.set_metadata("reply-with", create_hash())
    if in_replay_to is not None:
        msg.set_metadata("in-replay-to", in_replay_to)
