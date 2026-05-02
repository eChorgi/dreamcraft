from dreamcraft.app.common.messaging import Mailbox


class ActionOrchestrator:
    def __init__(self, inbox: Mailbox, outbox: Mailbox):
        self.inbox = inbox
        self.outbox = outbox
        