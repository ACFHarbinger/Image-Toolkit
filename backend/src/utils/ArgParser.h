#ifndef ARG_PARSER_H
#define ARG_PARSER_H

#include <string>
#include <vector>
#include <map>
#include "cxxopts.hpp" // Requires cxxopts dependency

/**
 * @brief Utility class to parse command line arguments using cxxopts.
 * * Replicates the structure of the Python parse_args() function.
 */
class ArgParser {
public:
    /**
     * @brief Structure to hold the result of the parsed arguments.
     */
    struct Arguments {
        std::string command;
        std::map<std::string, std::string> stringArgs;
        std::map<std::string, std::vector<std::string>> vectorArgs;
        std::map<std::string, bool> boolArgs;
        std::map<std::string, int> intArgs;
        std::map<std::string, std::vector<int>> intVectorArgs;
    };

    /**
     * @brief Initializes the main parser and subcommand structure.
     */
    ArgParser();

    /**
     * @brief Parses the raw command line arguments.
     * @param argc The argument count.
     * @param argv The argument values.
     * @return The Arguments struct containing the parsed values.
     */
    Arguments parseArgs(int argc, char** argv);

private:
    cxxopts::Options m_options;

    /**
     * @brief Helper to initialize a parser with common options.
     */
    cxxopts::Options createParser(const std::string& name, const std::string& description);

    /**
     * @brief Adds arguments specific to the 'convert' command.
     */
    void addConvertArgs(cxxopts::Options& options);

    /**
     * @brief Adds arguments specific to the 'merge' command.
     */
    void addMergeArgs(cxxopts::Options& options);

    /**
     * @brief Adds arguments specific to the 'delete' command.
     */
    void addDeleteArgs(cxxopts::Options& options);

    /**
     * @brief Adds arguments specific to the 'web_crawler' command.
     */
    void addCrawlerArgs(cxxopts::Options& options);
    
    /**
     * @brief Adds arguments specific to the 'gui' command.
     */
    void addGuiArgs(cxxopts::Options& options);

    /**
     * @brief Extracts and maps results from cxxopts::ParseResult into Arguments structure.
     */
    Arguments mapResults(const cxxopts::ParseResult& result, const std::string& command);
};

#endif // ARG_PARSER_H