"""
Dispatcher for Image-Toolkit CLI commands.
Connects parsed arguments to backend implementations.
"""

import os
from ..core.image_converter import ImageFormatConverter

def dispatch_core(args):
    command = args.get("core_command")
    if command == "convert":
        inputs = args.get("input")
        output = args.get("output")
        fmt = args.get("format")
        quality = args.get("quality")
        recursive = args.get("recursive")
        
        # Determine if single or batch
        if len(inputs) == 1 and os.path.isfile(inputs[0]):
            success = ImageFormatConverter.convert_single_image(
                image_path=inputs[0],
                output_name=output, # converter handles None
                format=fmt,
                # quality is not yet passed to rust backend but we can add it later
            )
            print(f"Conversion {'successful' if success else 'failed'}")
        else:
            # Batch conversion
            # If multiple inputs or a directory
            for input_path in inputs:
                if os.path.isdir(input_path):
                    results = ImageFormatConverter.convert_batch(
                        input_dir=input_path,
                        inputs_formats=["webp", "png", "jpg", "jpeg", "bmp", "gif", "tiff", "avif"],
                        output_dir=output,
                        output_format=fmt,
                        # recursive=recursive # TODO: add recursive to backend
                    )
                elif os.path.isfile(input_path):
                    success = ImageFormatConverter.convert_single_image(
                        image_path=input_path,
                        output_name=output,
                        format=fmt,
                    )
    elif command == "merge":
        print("Merge command not yet fully connected to CLI")
        # TODO: Implement merge dispatch

def dispatch_web(args):
    print("Web command not yet connected to CLI")

def dispatch_database(args):
    print("Database command not yet connected to CLI")

def dispatch_model(args):
    print("Model command not yet connected to CLI")

def dispatch_command(command, args):
    if command == "core":
        dispatch_core(args)
    elif command == "web":
        dispatch_web(args)
    elif command == "database":
        dispatch_database(args)
    elif command == "model":
        dispatch_model(args)
    else:
        print(f"Unknown command: {command}")
