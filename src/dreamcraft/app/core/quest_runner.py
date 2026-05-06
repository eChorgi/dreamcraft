from dreamcraft.app.core.messaging import Mailbox
from dreamcraft.app.core.quest_context import QuestContext


class QuestRunner:
    def __init__(self, inbox: Mailbox, outbox: Mailbox, context: QuestContext):
        self.inbox = inbox
        self.outbox = outbox
        self.context = context
        