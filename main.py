import io
import os
import sys
import signal
import pprint
import traceback
import psycopg2.extras

from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from backend.src.gui.MainWindow import MainWindow
from backend.src import (
    parse_args, FSETool, 
    ImageFormatConverter,
    PgvectorImageDatabase, 
    ImageMerger, ImageCrawler,
)


def _pretty_print_args(comm, opts, inner_comm=None):
    try:
        # Capture the pprint output
        printer = pprint.PrettyPrinter(width=1, indent=1, sort_dicts=False)
        buffer = io.StringIO()
        printer._stream = buffer # Redirect PrettyPrinter's internal stream
        printer.pprint(opts)
        output = buffer.getvalue()

        # Pretty print the run options
        lines = output.splitlines()
        lines[0] = lines[0].lstrip('{')
        lines[-1] = lines[-1].rstrip('}')
        formatted = comm + "{}".format(f' {inner_comm}' if inner_comm is not None else "") + \
            ": {\n" + "\n".join(f" {line}" for line in lines) + "\n}"
        print(formatted, end="\n\n")
    except Exception as e:
        raise Exception(f"Failed to pretty print arguments: {e}")


def main(comm, args):
    exit_code = 0
    try:
        _pretty_print_args(comm, args)
        if comm == 'convert':
            if 'input_formats' in args and len(args['input_formats']) > 0:
                _ = ImageFormatConverter.batch_convert_img_format(args['input_path'], args['input_formats'], args['output_path'], args['output_format'], args['delete'])
            else:
                _ = ImageFormatConverter.convert_img_format(args['input_path'], args['output_path'], args['output_format'], args['delete'])
        elif comm == 'delete':
            if 'target_extensions' in args and args['target_extensions'] is not None:
                _ = FSETool.delete_files_by_extensions(args['target_path'], args['target_extensions'])
            else:
                _ = FSETool.delete_path(args['target_path'])
        elif comm == 'merge':
            if len(args['input_path']) == 1 and 'input_formats' in args and len(args['input_formats']) > 0:
                _ = ImageMerger.merge_directory_images(args['input_path'][0], args['input_formats'], args['output_path'], args['direction'], args['grid_size'], args['spacing'])
            else:
                _ = ImageMerger.merge_images(args['input_path'], args['output_path'], args['direction'], args['grid_size'], args['spacing'])
        elif comm == 'web_crawler':
            crawler = ImageCrawler(
                url=args['url'],
                headless=args['headless'],
                download_dir=args['download_dir'],
                browser=args['browser'],
                skip_first=args['skip_first'],
                skip_last=args['skip_last']
            )
            exit_code = crawler.run()
        elif comm == 'gui':
            # This allows the Python interpreter to process signals (like SIGINT).
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            timer = QTimer()
            timer.start(100) # Check every 100 milliseconds
            timer.timeout.connect(lambda: None) # Do nothing, just wake up Python

            app = QApplication(sys.argv)
            path = Path(os.getcwd())
            parts = path.parts
            icon_file_path = os.path.join(Path(*parts[:parts.index('Image-Toolkit') + 1]), 
                                            'src', 'images', "image_toolkit_icon.png")
            try:
                # 1. Create a QIcon instance from the image file
                app_icon = QIcon(icon_file_path)
                
                # 2. Set the icon for the entire application
                # This ensures the icon appears in the taskbar and title bar.
                app.setWindowIcon(app_icon)
            except Exception as e:
                print(f"Warning: Failed to set application icon. Ensure '{icon_file_path}' exists. Error: {e}")
            w = MainWindow(dropdown=args['dropdown'])
            w.show()
            exit_code = app.exec()
        elif comm == 'database':
            return
    except KeyboardInterrupt:
        print("\nExiting due to Ctrl+C...")
        exit_code = 2
    except Exception as e:
        exit_code = 1
        traceback.print_exc(file=sys.stdout)
        print("###############" * 10 + '\n' + e)
        print(e)
    finally:
        sys.exit(exit_code)


if __name__ =="__main__":
    main(*parse_args())