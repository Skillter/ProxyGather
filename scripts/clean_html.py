
#!/usr/bin/env python3
"""
A Python script to remove boilerplate and redundant code from an HTML file,
reducing its size while keeping the core DOM structure intact.
"""

import argparse
import os
from html.parser import HTMLParser

class HTMLCleaner(HTMLParser):
    """
    A custom HTML parser to remove unwanted tags, attributes, and content.
    Optionally formats the output for readability.
    """
    def __init__(self, pretty_print=False, remove_classes=False, remove_links=False):
        super().__init__()
        self.cleaned_html = []
        self.skip_content = False
        self.pretty_print = pretty_print
        self.remove_classes = remove_classes
        self.remove_links = remove_links
        self.indent_level = 0

        # Tags whose content will be completely removed
        self.tags_to_skip = {'script', 'style', 'meta', 'link', 'noscript', 'base'}

        # Tags that do not contain other elements and don't need a closing tag newline
        self.self_closing_tags = {'br', 'hr', 'img', 'input', 'link', 'meta'}

        # Tags that are typically inline and shouldn't be surrounded by newlines
        self.inline_tags = {
            'a', 'span', 'b', 'strong', 'i', 'em', 'u', 'sub', 'sup',
            'button', 'label', 'img', 'code', 'small'
        }

        # Whitelist of attributes to preserve on tags
        self.attrs_to_keep = {
            'id', 'class', 'href', 'src', 'alt', 'title', 'name',
            'value', 'type', 'placeholder', 'role', 'for', 'rel', 'target'
        }
        
        # Attributes that contain URLs/links
        self.url_attributes = {
            'href', 'src', 'action', 'data', 'poster', 'srcset',
            'cite', 'formaction', 'icon', 'manifest', 'archive',
            'background', 'codebase', 'classid', 'longdesc', 'profile', 'usemap'
        }

        # Update attrs_to_keep based on options
        if self.remove_classes:
            self.attrs_to_keep.discard('class')
        
        if self.remove_links:
            # Remove URL-containing attributes from the whitelist
            self.attrs_to_keep = self.attrs_to_keep - self.url_attributes

    def handle_starttag(self, tag, attrs):
        if tag in self.tags_to_skip:
            self.skip_content = True
            return

        if self.pretty_print and tag not in self.inline_tags and self.cleaned_html:
            self.cleaned_html.append('\n' + '  ' * self.indent_level)

        # Filter attributes based on settings
        filtered_attrs = []
        for attr, val in attrs:
            # Skip class attributes if remove_classes is enabled
            if self.remove_classes and attr == 'class':
                continue
            
            # Skip URL attributes if remove_links is enabled
            if self.remove_links and attr in self.url_attributes:
                continue
            
            # Handle data- and aria- attributes with URL checking
            if attr.startswith(('data-', 'aria-')):
                # If removing links, check if the value looks like a URL
                if self.remove_links and val and self._is_url_like(val):
                    continue
                filtered_attrs.append((attr, val))
            elif attr in self.attrs_to_keep:
                filtered_attrs.append((attr, val))

        # Reconstruct the tag string
        attr_str = ' '.join(f'{key}="{val}"' for key, val in filtered_attrs)
        tag_str = f'<{tag}{" " if attr_str else ""}{attr_str}>'
        self.cleaned_html.append(tag_str)

        if self.pretty_print and tag not in self.self_closing_tags:
            self.indent_level += 1

    def handle_endtag(self, tag):
        if tag in self.tags_to_skip:
            self.skip_content = False
            return

        if self.pretty_print and tag not in self.self_closing_tags:
            self.indent_level -= 1

        if self.pretty_print and tag not in self.inline_tags:
            self.cleaned_html.append('\n' + '  ' * self.indent_level)

        self.cleaned_html.append(f'</{tag}>')

    def handle_data(self, data):
        # Skip content of certain tags or if it's just whitespace
        if self.skip_content or data.isspace():
            return

        stripped_data = data.strip()
        
        # If removing links, filter out URL-like content from text
        if stripped_data and self.remove_links:
            stripped_data = self._filter_urls_from_text(stripped_data)
        
        if stripped_data:
            if self.pretty_print:
                # Indent text content if it's on a new line
                if self.cleaned_html and self.cleaned_html[-1].endswith('\n' + '  ' * self.indent_level):
                     self.cleaned_html.append(stripped_data)
                else:
                    self.cleaned_html.append('\n' + '  ' * self.indent_level + stripped_data)
            else:
                self.cleaned_html.append(stripped_data)

    def handle_comment(self, data):
        # Skip comments entirely
        pass

    def _is_url_like(self, value):
        """Check if a value looks like a URL."""
        url_indicators = ('http://', 'https://', 'ftp://', 'mailto:', '//', 'www.')
        return any(value.lower().startswith(indicator) for indicator in url_indicators)
    
    def _filter_urls_from_text(self, text):
        """Remove URLs from text content."""
        import re
        # Pattern to match URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        # Replace URLs with empty string
        text = re.sub(url_pattern, '', text)
        # Also remove www. patterns
        www_pattern = r'www\.[^\s<>"{}|\\^`\[\]]+'
        text = re.sub(www_pattern, '', text)
        # Clean up multiple spaces that might result
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_cleaned_html(self):
        """Returns the cleaned HTML as a single string."""
        return ''.join(self.cleaned_html).strip()


def main():
    """Main function to parse arguments and run the cleaning process."""
    parser = argparse.ArgumentParser(
        description="Cleans an HTML file by removing scripts, styles, comments, and unnecessary attributes.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Path to the HTML file to be cleaned."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save the cleaned HTML file.\n(default: 'cleaned_[input_file_name]')",
        default=None
    )
    parser.add_argument(
        "-i", "--in-place",
        action="store_true",
        help="Modify the input file directly (overwrite). Use with caution."
    )
    parser.add_argument(
        "-p", "--pretty",
        action="store_true",
        help="Format the output HTML with indentation for readability."
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite of the output file if it already exists."
    )
    parser.add_argument(
        "-c", "--remove-classes",
        action="store_true",
        help="Remove all class attributes from HTML elements."
    )
    parser.add_argument(
        "-l", "--remove-links",
        action="store_true",
        help="Remove all URLs and links from the HTML (href, src, etc.)."
    )

    args = parser.parse_args()

    # Determine the output path
    if args.in_place:
        output_path = args.input_file
    elif args.output:
        output_path = args.output
    else:
        dirname, filename = os.path.split(args.input_file)
        output_path = os.path.join(dirname, f"cleaned_{filename}")

    # Check for file existence before proceeding
    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'")
        return

    if os.path.exists(output_path) and not args.force and not args.in_place:
        print(f"Error: Output file '{output_path}' already exists. Use -f or --force to overwrite.")
        return

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        cleaner = HTMLCleaner(
            pretty_print=args.pretty,
            remove_classes=args.remove_classes,
            remove_links=args.remove_links
        )
        cleaner.feed(html_content)
        cleaned_html = cleaner.get_cleaned_html()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_html)

        print(f"✓ Successfully cleaned '{args.input_file}'")
        print(f"  Saved to '{output_path}'")
        
        # Report which options were used
        options_used = []
        if args.pretty:
            options_used.append("pretty formatting")
        if args.remove_classes:
            options_used.append("class removal")
        if args.remove_links:
            options_used.append("link/URL removal")
        
        if options_used:
            print(f"  Options applied: {', '.join(options_used)}")

        input_size = os.path.getsize(args.input_file)
        output_size = os.path.getsize(output_path)
        if input_size > 0:
            reduction = 100 - (output_size / input_size * 100)
            print(f"\nOriginal size: {input_size / 1024:.2f} KB")
            print(f"Cleaned size:  {output_size / 1024:.2f} KB")
            print(f"Size reduction: {reduction:.2f}%")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

# --- Main execution ---
if __name__ == "__main__":
    main()
