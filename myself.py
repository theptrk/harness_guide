from pprint import pprint

print("harnessing")

class HistoryHandler():
    def __init__(self):
        self.history = []

    def add_item(self, role, message):
        x = { "role": role, "message": message }
        self.history.append(x)

def date_tool():
    return "12:45 or the correct time"

tools_calling_index = {
    "date_tool": date_tool
    # others later
}

mock_messages1 = [
    "sky is blue"
]

mock_messages2 = [
    "need_tool",
    "its 12:45 in Tokyo"
]

mock_messages3 = [
    "need_tool",
    "need_tool",
    "need_tool",
    "its 12:45 in Tokyo, 4:45 in London, 3:45 in Prague"
]

class LLM:
    def chat(input):
        pass

class Agent():
    def __init__(self):
        self.hh = HistoryHandler()
        self.mock_messages = mock_messages1

    def llm(self):
        return self.mock_messages.pop(0)

    def handle_message(self, x):
        self.hh.add_item("user", x)

        y = self.llm()

        while y == "need_tool":
            print("  thought > ", y)
            self.hh.add_item("tool request", y)

            tool_output = tool_calling_index["date_tool"]()
            print("  tool output > ", tool_output)
            self.hh.add_item("tool_output", tool_output)
            # overwrite the y above
            y = self.llm()

        self.hh.add_item("assistant", y)
        print("Bot > ", y)

a = Agent()
while True:
    x = input("You > ")

    if x:
        a.handle_message(x)
    else:
        pprint(a.hh.history)
