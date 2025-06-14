import argparse
import os
import sys

def remove_duplicate_lines(input_filepath):
    """
    Reads a file, removes duplicate lines while preserving order,
    and writes the result to a new file.
    """
    # 1. Check if the input file exists
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at '{input_filepath}'")
        sys.exit(1)

    print(f"Processing file: {input_filepath}")

    try:
        # 2. Read all lines from the file into a list
        with open(input_filepath, 'r', encoding='utf-8') as f_in:
            lines = f_in.readlines()

        # 3. Use a set to track seen lines for efficiency, and a list to store unique lines
        #    This preserves the order of the first occurrence of each line.
        seen_lines = set()
        unique_lines = []
        duplicate_count = 0

        for line in lines:
            if line not in seen_lines:
                unique_lines.append(line)
                seen_lines.add(line)
            else:
                duplicate_count += 1
        
        # 4. Define the output filename
        #    e.g., 'data.txt' -> 'data_unique.txt'
        base, ext = os.path.splitext(input_filepath)
        output_filepath = f"{base}_unique{ext}"

        # 5. Write the unique lines to the new file
        with open(output_filepath, 'w', encoding='utf-8') as f_out:
            f_out.writelines(unique_lines)

        # 6. Print a summary report
        print("-" * 20)
        print(f"Original line count: {len(lines)}")
        print(f"Unique line count:   {len(unique_lines)}")
        print(f"Duplicates removed:  {duplicate_count}")
        print(f"\nSuccess! Result saved to: '{output_filepath}'")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

def main():
    """
    Parses command-line arguments and calls the main function.
    """
    parser = argparse.ArgumentParser(
        description="A script to remove duplicate lines from a text file.",
        formatter_class=argparse.RawTextHelpFormatter # For better help text formatting
    )

    parser.add_argument(
        '--file',
        dest='filepath', # The name of the variable to store the argument
        required=True,
        help="The path to the file you want to process."
    )

    args = parser.parse_args()
    remove_duplicate_lines(args.filepath)

if __name__ == "__main__":
    main()