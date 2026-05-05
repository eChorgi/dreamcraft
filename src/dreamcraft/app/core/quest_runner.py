from dreamcraft.app.common.messaging import Mailbox


class QuestRunner:
    def __init__(self, inbox: Mailbox, outbox: Mailbox):
        self.inbox = inbox
        self.outbox = outbox
        