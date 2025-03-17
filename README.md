# Fixter: AI-CMD Tool

Fixter is an experimental AI-powered command-line tool designed to assist developers with various coding tasks. It uses a multi-agent architecture to dynamically handle different types of queries and maintains context across sessions with a sophisticated memory system.

> ⚠️ **EXPERIMENTAL**: This project is in early development, and features may change. Use at your own risk.

## Features

### Multi-Agent Architecture
- **Coordinator Agent**: Routes queries to the appropriate specialized agent
- **Extraction Agent**: Handles file and repository content extraction
- **Conversation Agent**: Manages general inquiries and reasoning tasks

### Memory Systems
- **Session Memory**: Maintains context within a terminal session
- **Entity Tracking**: Automatically identifies and remembers files, directories, and other entities
- **Persistent Storage**: Session data is preserved between runs

### Content Extraction
- Local file extraction with filtering by extension
- GitHub repository content extraction (with and without cloning)
- Content copying to clipboard or saving to file

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/fixter.git
cd fixter
```

2. Create and configure the environment file:

```bash
cp .env.example .env
# Edit .env with your favorite editor and add your API keys
```

3. Install the package:

```bash
pip install -e .
```

## Configuration

Fixter requires an OpenAI API key to function. Add your key to the `.env` file:

```bash
OPENAI_API_KEY=your_api_key_here
```

## Usage

### Basic Commands

Query the AI assistant:

```bash
fixter ai "What is a decorator in Python?"
```

Extract code from a directory:

```bash
fixter ai "Extract all Python files from /path/to/your/project"
```

Get code from a GitHub repository:

```bash
fixter ai "Extract the Python files from https://github.com/username/repo"
```

### Session Management

List available sessions:

```bash
fixter sessions
```

Clear the current session:

```bash
fixter clear-session
```

### Variable Management

Set variables for frequent use:

```bash
fixter set project_path=/path/to/your/project
```

Use variables in commands:

```bash
fixter ai "What files are in {project_path}?"
```

List defined variables:

```bash
fixter vars
```

## How It Works

1. **Query Classification**: Each request is classified to determine the most appropriate agent.
2. **Agent Processing**: The specialized agent processes the request using appropriate tools.
3. **Memory Integration**: Session data is updated with new information from the interaction.
4. **Response Generation**: The agent formulates and returns a response.

## Limitations

- Currently supports only OpenAI models (default: gpt-4o-mini)
- Some features like memory reflection are experimental
- Performance depends on the quality and limits of the underlying AI model

## Future Development

- Additional specialized agents
- Support for more AI models
- Improved memory systems and terminal context handling

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

For questions or suggestions, you can also contact me at ravi.l@northeastern.edu

---

*Note: This is an experimental tool. Please report any issues or suggestions in the GitHub issues section.*
