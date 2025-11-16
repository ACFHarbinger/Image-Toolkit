#include "ArgParser.h"
#include "Definitions.h"
#include <iostream>
#include <sstream>
#include <algorithm>

using namespace std;
namespace def = Definitions;

// --- Helper Functions ---

// Function to check if a required argument is present
template <typename T>
bool checkRequired(const cxxopts::ParseResult& result, const std::string& name, const std::string& command) {
    if (!result.count(name)) {
        cerr << "Argument error: --" << name << " is required for command '" << command << "'" << endl;
        return false;
    }
    return true;
}

// --- ArgParser Implementation ---

ArgParser::ArgParser() 
    : m_options("Image Toolkit", "Image database and edit toolkit.") 
{
    // Cxxopts simplifies subparsers by letting the first unmatched argument determine the command.
    // The main options object must capture this command argument first.
    m_options.add_option("", "command", "Command to execute (convert, merge, delete, web_crawler, gui)", 
                         cxxopts::value<std::string>(), "");
    m_options.allow_unrecognised_options();
    m_options.add_option("", "h", "help", cxxopts::value<bool>(), "Display this help menu");
}

ArgParser::Arguments ArgParser::parseArgs(int argc, char** argv) {
    try {
        auto result = m_options.parse(argc, argv);

        if (result.count("h")) {
            // Re-show help using the specific command context if provided
            if (argc > 1) {
                // Try to parse command if present
                std::string command = argv[1];
                cxxopts::Options commandOptions("Command " + command, "Arguments for " + command);
                if (command == "convert") addConvertArgs(commandOptions);
                else if (command == "merge") addMergeArgs(commandOptions);
                else if (command == "delete") addDeleteArgs(commandOptions);
                else if (command == "web_crawler") addCrawlerArgs(commandOptions);
                else if (command == "gui") addGuiArgs(commandOptions);
                
                std::cout << commandOptions.help() << std::endl;
            } else {
                 std::cout << m_options.help() << std::endl;
            }
            throw std::runtime_error("Help displayed.");
        }

        if (!result.count("command")) {
            m_options.help();
            throw std::runtime_error("No command specified.");
        }

        std::string command = result["command"].as<std::string>();
        cxxopts::Options commandOptions("Command " + command, "Arguments for " + command);

        if (command == "convert") addConvertArgs(commandOptions);
        else if (command == "merge") addMergeArgs(commandOptions);
        else if (command == "delete") addDeleteArgs(commandOptions);
        else if (command == "web_crawler") addCrawlerArgs(commandOptions);
        else if (command == "gui") addGuiArgs(commandOptions);
        else throw std::runtime_error("Unknown command: " + command);
        
        // Re-parse remaining arguments for the specific command options
        auto finalResult = commandOptions.parse(argc, argv);
        
        // --- Custom Requirement Checks ---
        if (command == "convert" && !checkRequired<std::string>(finalResult, "output_format", command)) throw std::runtime_error("Missing required args.");
        if (command == "convert" && !checkRequired<std::string>(finalResult, "input_path", command)) throw std::runtime_error("Missing required args.");
        if (command == "merge" && !checkRequired<std::string>(finalResult, "direction", command)) throw std::runtime_error("Missing required args.");
        if (command == "merge" && !checkRequired<std::vector<std::string>>(finalResult, "input_path", command)) throw std::runtime_error("Missing required args.");
        if (command == "delete" && !checkRequired<std::string>(finalResult, "target_path", command)) throw std::runtime_error("Missing required args.");
        if (command == "web_crawler" && !checkRequired<std::string>(finalResult, "url", command)) throw std::runtime_error("Missing required args.");

        return mapResults(finalResult, command);

    } catch (const cxxopts::OptionException& e) {
        cerr << "Error parsing arguments: " << e.what() << endl;
        throw;
    } catch (const std::exception& e) {
        cerr << "Error: " << e.what() << endl;
        throw;
    }
}

void ArgParser::addConvertArgs(cxxopts::Options& options) {
    options.add_options()
        ("output_format", "The format to convert the image(s) to", cxxopts::value<std::string>()->default_value("png"))
        ("input_path", "The path to the input image/directory which we want to transform", cxxopts::value<std::string>())
        ("output_path", "The path to write the transformed image(s) to", cxxopts::value<std::string>()->default_value(""))
        ("input_formats", "Formats of the input images we want to transform (define when input_path is a directory)", cxxopts::value<std::vector<std::string>>()->default_value(""))
        ("delete", "Delete image(s) that were converted to new format (Default: true)", cxxopts::value<bool>()->default_value("true")->implicit_value("false"));
}

void ArgParser::addMergeArgs(cxxopts::Options& options) {
    options.add_options()
        ("direction", "The direction to merge the images: 'horizontal'|'vertical'|'grid'", cxxopts::value<std::string>())
        ("input_path", "The path to the input images (or directory with the images) which we want to merge", cxxopts::value<std::vector<std::string>>())
        ("output_path", "The path to write the merged image to", cxxopts::value<std::string>()->default_value(""))
        ("input_formats", "Formats of the input images we want to transform (define when input_path is a directory)", cxxopts::value<std::vector<std::string>>()->default_value(""))
        ("spacing", "Spacing between images when merging", cxxopts::value<int>()->default_value("0"))
        ("grid_size", "Size of the grid (define if direction is 'grid')", cxxopts::value<std::vector<int>>()->default_values({"0", "0"}));
}

void ArgParser::addDeleteArgs(cxxopts::Options& options) {
    options.add_options()
        ("target_path", "The path to the target file/directory we want to delete", cxxopts::value<std::string>())
        ("target_extensions", "The extension of files to delete (define when target_path is a directory)", cxxopts::value<std::vector<std::string>>()->default_value(""));
}

void ArgParser::addCrawlerArgs(cxxopts::Options& options) {
    // Note: The browser choices must be verified against Definitions::WC_BROWSERS at runtime.
    options.add_options()
        ("browser", "The browser to use for crawling the web (brave|firefox|chrome|edge|safari)", cxxopts::value<std::string>()->default_value("brave"))
        ("headless", "Initialize browser in headless mode", cxxopts::value<bool>()->implicit_value("true")->default_value("false"))
        ("download_dir", "Name of the directory to save the download(s) to", cxxopts::value<std::string>()->default_value("downloads"))
        ("screenshot_dir", "Name of the directory to save the screenshot(s) to", cxxopts::value<std::string>()->default_value(""))
        ("url", "The URL to crawl through", cxxopts::value<std::string>()) // Changed type from int to string
        ("skip_first", "The amount of images to skip at the start of the webpage", cxxopts::value<int>()->default_value("0"))
        ("skip_last", "The amount of images to skip at the end of the webpage", cxxopts::value<int>()->default_value("9"));
}

void ArgParser::addGuiArgs(cxxopts::Options& options) {
    options.add_options()
        ("no_dropdown", "Disable dropdown buttons for optional fields", cxxopts::value<bool>()->implicit_value("true")->default_value("false"));
}

ArgParser::Arguments ArgParser::mapResults(const cxxopts::ParseResult& result, const std::string& command) {
    Arguments args;
    args.command = command;

    // Use is_null() check for optional arguments that were not supplied and must be NULL/empty.
    
    // --- Convert Command ---
    if (command == "convert") {
        args.stringArgs["output_format"] = result["output_format"].as<std::string>();
        args.stringArgs["input_path"] = result["input_path"].as<std::string>();
        args.stringArgs["output_path"] = result.count("output_path") ? result["output_path"].as<std::string>() : "";
        args.vectorArgs["input_formats"] = result.count("input_formats") ? result["input_formats"].as<std::vector<std::string>>() : std::vector<std::string>{};
        args.boolArgs["delete"] = result["delete"].as<bool>();
    }
    
    // --- Merge Command ---
    else if (command == "merge") {
        args.stringArgs["direction"] = result["direction"].as<std::string>();
        args.vectorArgs["input_path"] = result["input_path"].as<std::vector<std::string>>();
        args.stringArgs["output_path"] = result.count("output_path") ? result["output_path"].as<std::string>() : "";
        args.vectorArgs["input_formats"] = result.count("input_formats") ? result["input_formats"].as<std::vector<std::string>>() : std::vector<std::string>{};
        args.intArgs["spacing"] = result["spacing"].as<int>();
        args.intVectorArgs["grid_size"] = result.count("grid_size") ? result["grid_size"].as<std::vector<int>>() : std::vector<int>{0, 0};
    }
    
    // --- Delete Command ---
    else if (command == "delete") {
        args.stringArgs["target_path"] = result["target_path"].as<std::string>();
        args.vectorArgs["target_extensions"] = result.count("target_extensions") ? result["target_extensions"].as<std::vector<std::string>>() : std::vector<std::string>{};
    }
    
    // --- Web Crawler Command ---
    else if (command == "web_crawler") {
        args.stringArgs["browser"] = result["browser"].as<std::string>();
        args.boolArgs["headless"] = result["headless"].as<bool>();
        args.stringArgs["download_dir"] = result["download_dir"].as<std::string>();
        args.stringArgs["screenshot_dir"] = result.count("screenshot_dir") ? result["screenshot_dir"].as<std::string>() : "";
        args.stringArgs["url"] = result["url"].as<std::string>();
        args.intArgs["skip_first"] = result["skip_first"].as<int>();
        args.intArgs["skip_last"] = result["skip_last"].as<int>();
    }
    
    // --- GUI Command ---
    else if (command == "gui") {
        args.boolArgs["no_dropdown"] = result["no_dropdown"].as<bool>();
    }

    return args;
}