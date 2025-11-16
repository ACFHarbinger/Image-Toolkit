#include "gtest/gtest.h"
#include "../src/utils/ArgParser.h"
#include <vector>
#include <string>

// Helper class to manage argc and argv for testing
class ArgvManager {
public:
    ArgvManager(const std::vector<std::string>& args) {
        m_argv.reserve(args.size());
        for (const auto& arg : args) {
            m_argv.push_back(const_cast<char*>(arg.c_str()));
        }
        m_argc = m_argv.size();
    }

    int argc() const { return m_argc; }
    char** argv() { return m_argv.data(); }

private:
    int m_argc;
    std::vector<char*> m_argv;
};

TEST(ArgParserTest, ParseGUI) {
    ArgvManager args({"./main", "gui", "--no_dropdown"});
    ArgParser parser;
    auto result = parser.parseArgs(args.argc(), args.argv());

    ASSERT_EQ(result.command, "gui");
    ASSERT_TRUE(result.boolArgs["no_dropdown"]);
}

TEST(ArgParserTest, ParseConvert) {
    ArgvManager args({"./main", "convert", "--input_path", "in.png", "--output_format", "jpg", "--delete"});
    ArgParser parser;
    auto result = parser.parseArgs(args.argc(), args.argv());

    ASSERT_EQ(result.command, "convert");
    ASSERT_EQ(result.stringArgs["input_path"], "in.png");
    ASSERT_EQ(result.stringArgs["output_format"], "jpg");
    ASSERT_FALSE(result.boolArgs["delete"]); // --delete is store_false, so flag presence means false
}

TEST(ArgParserTest, ParseMerge) {
    ArgvManager args({"./main", "merge", "--direction", "grid", "--input_path", "a.png", "b.png", "--grid_size", "2", "1", "--spacing", "10"});
    ArgParser parser;
    auto result = parser.parseArgs(args.argc(), args.argv());

    ASSERT_EQ(result.command, "merge");
    ASSERT_EQ(result.stringArgs["direction"], "grid");
    ASSERT_EQ(result.vectorArgs["input_path"].size(), 2);
    ASSERT_EQ(result.vectorArgs["input_path"][0], "a.png");
    ASSERT_EQ(result.intArgs["spacing"], 10);
    ASSERT_EQ(result.intVectorArgs["grid_size"][0], 2);
    ASSERT_EQ(result.intVectorArgs["grid_size"][1], 1);
}

TEST(ArgParserTest, ParseCrawler) {
    ArgvManager args({"./main", "web_crawler", "--url", "http://test.com", "--headless"});
    ArgParser parser;
    auto result = parser.parseArgs(args.argc(), args.argv());

    ASSERT_EQ(result.command, "web_crawler");
    ASSERT_EQ(result.stringArgs["url"], "http://test.com");
    ASSERT_TRUE(result.boolArgs["headless"]);
}

TEST(ArgParserTest, ParseMissingRequired) {
    ArgvManager args({"./main", "convert"}); // Missing --input_path and --output_format
    ArgParser parser;
    
    // Expect the parser to throw an exception
    ASSERT_THROW(parser.parseArgs(args.argc(), args.argv()), std::runtime_error);
}

TEST(ArgParserTest, ParseHelp) {
    ArgvManager args({"./main", "-h"});
    ArgParser parser;
    
    // Help throws a specific exception to stop execution
    ASSERT_THROW(parser.parseArgs(args.argc(), args.argv()), std::runtime_error);
}