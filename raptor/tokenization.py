import re


class SimpleTokenizer:
    def encode(self, text):
        text = text or ""
        tokens = re.findall(r"[0-9A-Za-z가-힣]+|[^\s]", text)
        return list(range(len(tokens)))


def get_tokenizer(name="cl100k_base"):
    try:
        import tiktoken

        return tiktoken.get_encoding(name)
    except ImportError:
        return SimpleTokenizer()
