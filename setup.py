from setuptools import setup, find_packages
import os

readme_path = "README.md"
long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="fixter",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "fixter=fixter.cli:main",
        ],
    },
    install_requires=[
        "langchain",
        "langgraph",
        "openai",
        "requests",
        "pyperclip",
        "python-dotenv",
        "langchain_google_genai",
        "langchain_openai",
        "langchain_community",
        "langchain_core",
        "langchain_ollama",
        "tavily-python",
        "psutil",  
        "pydantic",  
    ],
    python_requires='>=3.8',
    author="Lakshminarayanan Ravi",
    description="An AI-powered command-line tool for coding assistance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/fixter",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)