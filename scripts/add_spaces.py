import re

def format_subtitle_spacing(input_file, output_file=None):
    if output_file is None:
        output_file = input_file
    
    def process_text(text):
        if ' --> ' in text or text.strip().isdigit():
            return text
            
        text = text.replace(r'\N', '__NEWLINE__')
        text = text.replace('……', '⋯⋯')
        
        half_width_punctuation = ['-', '=', '+', '*', '/', '\\']
        for punct in half_width_punctuation:
            text = re.sub(re.escape(punct), f' {punct} ', text)
        
        patterns = [
            (r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2'),
            (r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2'),
            (r'([\u4e00-\u9fff])([0-9])', r'\1 \2'),
            (r'([0-9])([\u4e00-\u9fff])', r'\1 \2')
        ]
        
        for pattern, repl in patterns:
            text = re.sub(pattern, repl, text)
            
        text = text.replace('__NEWLINE__', r'\N')
        text = re.sub(r'\s+', ' ', text)
        return text.strip() + '\n'  # 保留換行符號

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    processed_lines = [process_text(line) for line in lines]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(processed_lines)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python format_subtitle.py <input_file> [output_file]')
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    format_subtitle_spacing(input_file, output_file)