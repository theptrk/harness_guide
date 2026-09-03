mock_messages1 = [
    "sky is blue",
    "green is green"
]

mock_messages2 = [
    "need_tool",
    "need_tool",
    "its 12:45 in Tokyo, 7:45 in Sydney"
]


class Agent():
    def __init__(self):
        self.mock_messages = mock_messages2

    def llm(self):
        return self.mock_messages.pop(0)

    def call_tool(self):
        return "12:45"

    def handle_message(self, x):
        # calls llm, maybe tool call, until enough info, answers
        y = self.llm()

        while y == "need_tool":
            # call_tool("tool_name", args)
            tool_output = self.call_tool()
            print("  tool output:", tool_output)
            y = self.llm()

        print("Bot >", y)


a = Agent()
while True:
    x = input("You > ")
    a.handle_message(x)
