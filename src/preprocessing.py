import re

class Preprocessor:
    def clean_code(self, code):
        # Remove extra blank lines
        code = re.sub(r'\n{3,}', '\n\n', code)
        # Remove trailing whitespace
        lines = [line.rstrip() for line in code.splitlines()]
        return '\n'.join(lines)

    def remove_comments(self, code):
        lines = code.splitlines()
        cleaned = []
        for line in lines:
            if not line.strip().startswith('#'):
                cleaned.append(line)
        return '\n'.join(cleaned)

    def normalize_indentation(self, code):
        lines = code.splitlines()
        normalized = []
        for line in lines:
            # Replace tabs with 4 spaces
            line = line.replace('\t', '    ')
            normalized.append(line)
        return '\n'.join(normalized)

    def extract_tokens(self, code):
        tokens = re.findall(r'\b\w+\b', code)
        return tokens

    def preprocess(self, code):
        code = self.clean_code(code)
        code = self.normalize_indentation(code)
        tokens = self.extract_tokens(code)
        return {
            'cleaned_code': code,
            'tokens': tokens,
            'token_count': len(tokens)
        }

if __name__ == "__main__":
    preprocessor = Preprocessor()
    sample = '''
def   hello():
	print("world")


'''
    result = preprocessor.preprocess(sample)
    print("✅ Preprocessing complete!")
    print(f"Tokens: {result['token_count']}")