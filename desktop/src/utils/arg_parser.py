import argparse

from .definitions import WC_BROWSERS


def parse_args():
    # Convert image format
    convert_parser = argparse.ArgumentParser(add_help=False)
    convert_parser.add_argument('--output_format', type=str, default='png', required=True, help="The format to convert the image(s) to")
    convert_parser.add_argument('--input_path', type=str, required=True, help="The path to the input image/directory which we want to transform")
    convert_parser.add_argument('--output_path', type=str, default=None, help="The path to write the transformed image(s) to")
    convert_parser.add_argument('--input_formats', type=str, nargs='*', help="Formats of the input images we want to transform (define when input_path is a directory)")
    convert_parser.add_argument('--delete', action='store_false', help="Delete image(s) that were converted to new format")

    # Merge multiple images into one
    merge_parser = argparse.ArgumentParser(add_help=False)
    merge_parser.add_argument('--direction', type=str, required=True, help="The direction to merge the images: 'horizontal'|'vertical'|'grid'")
    merge_parser.add_argument('--input_path', type=str, nargs='+', required=True, help="The path to the input images (or directory with the images) which we want to merge")
    merge_parser.add_argument('--output_path', type=str, nargs='?', help="The path to write the merged image to")
    merge_parser.add_argument('--input_formats', type=str, nargs='*', help="Formats of the input images we want to transform (define when input_path is a directory)")
    merge_parser.add_argument('--spacing', type=int, default=0, help="Spacing between images when merging")
    merge_parser.add_argument('--grid_size', type=int, nargs=2, metavar=('rows', 'columns'), help="Size of the grid (define if direction is 'grid')")

    # Remove output files and directories
    delete_parser = argparse.ArgumentParser(add_help=False)
    delete_parser.add_argument('--target_path', type=str, required=True, help="The path to the target file/directory we want to delete")
    delete_parser.add_argument('--target_extensions', type=str, nargs='*', help="The extension of files to delete (define when target_path is a directory)")

    # Search for images
    search_parser = argparse.ArgumentParser(add_help=False)
    search_parser.add_argument('--input_directory', type=str, required=True, help="The path to the directory with the images")
    search_parser.add_argument('--names', type=str, nargs='+', help="Names of the entities present in the images")
    search_parser.add_argument('--tags', type=str, nargs='*', help="Image description tags")

    # Image web crawler
    crawlers_parser = argparse.ArgumentParser(add_help=False)
    crawlers_parser.add_argument('--browser', type=str, default='edge', choices=WC_BROWSERS, help="The browser to use for crawling the web")
    crawlers_parser.add_argument('--headless', action='store_true', help="Initialize browser in headless mode")
    crawlers_parser.add_argument('--download_dir', type=str, default='downloads', help="Name of the directory to save the download(s) to")
    crawlers_parser.add_argument('--screenshot_dir', type=str, default=None, help="Name of the directory to save the screenshot(s) to")
    crawlers_parser.add_argument('--url', type=int, required=True, help="The URL to crawl through")
    crawlers_parser.add_argument('--skip_first', type=int, default=0, help="The amount of images to skip at the start of the webpage")
    crawlers_parser.add_argument('--skip_last', type=int, default=9, help="The amount of images to skip at the end of the webpage")

    # GUI
    gui_parser = argparse.ArgumentParser(add_help=False)
    gui_parser.add_argument('--dropdown', type=bool, default=True, help="Use dropdown buttons for optional fields")

    # Main parser
    parser = argparse.ArgumentParser(description="Image database and edit toolkit.")
    subparsers = parser.add_subparsers(help="command", dest="command")

    # Add subparsers
    convert_subparser = subparsers.add_parser('convert', parents=[convert_parser], add_help=False)
    merge_subparser = subparsers.add_parser('merge', parents=[merge_parser], add_help=False)
    delete_subparser = subparsers.add_parser('delete', parents=[delete_parser], add_help=False)
    crawlers_subparser = subparsers.add_parser('web_crawler', parents=[crawlers_parser], add_help=False)
    gui_subparser = subparsers.add_parser('gui', parents=[gui_parser], add_help=False)

    args = vars(parser.parse_args())
    command = args.pop('command')
    if command == 'convert':
        return command, args
    elif command == 'delete':
        return command, args
    elif command == 'merge':
        return command, args
    elif command == 'search':
        return command, args
    elif command == 'web_crawler':
        return command, args
    elif command == 'gui':
        return command, args
    
    raise argparse.ArgumentError("Argument error: unknown command " + args['command'])
