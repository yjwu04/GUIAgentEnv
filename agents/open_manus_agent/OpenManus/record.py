class outputRecord:
    def __init__(self):
        self.messages = []

    def clear(self):
        self.messages = []

    def add_message(self, message):
        print(message)
        self.messages.append(message)
        print(self.messages)

output_record = outputRecord()
