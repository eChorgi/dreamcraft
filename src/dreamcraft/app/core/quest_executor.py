from dreamcraft.app.core.messaging import Mailbox
from dreamcraft.app.core.quest_context import QuestContext


class QuestExecutor:
    def __init__(self, inbox: Mailbox, orchestrator_inbox: Mailbox, context: QuestContext):
        self.inbox = inbox
        self.orchestrator_inbox = orchestrator_inbox
        self.context = context
        