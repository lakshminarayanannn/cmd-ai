from langchain.agents import tool, create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import TavilySearchResults
from typing import Annotated, TypedDict, Union
from langchain_core.agents import AgentAction, AgentFinish
from dotenv import load_dotenv
from langchain import hub
import operator
import requests
import datetime
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
import os 
import pyperclip
import datetime
import subprocess

from fixter.config import get_master_folder

load_dotenv()

@tool
def extract_git_content(git_url: str, extensions: list = None, clone: bool = False, clipboard_only: bool = True):
    """
    Extracts content from a GitHub repository by either cloning the repository locally or fetching directly via GitHub's API.

    Parameters:
    - git_url (str): The URL of the GitHub repository (ending with '.git' is optional).
    - extensions (list, optional): A list of file extensions to filter files to be extracted. Defaults to an empty list (no filtering).
    - clone (bool, optional): If True, the repository will be cloned locally before extracting files. Defaults to False.
    - clipboard_only (bool, optional): If True, extracted content will be copied only to the clipboard and not saved as a file. Defaults to True.

    Returns:
    - str: The concatenated content extracted from the repository.

    Raises:
    - Exception: If no matching files are found in the cloned repository or GitHub repository via API.
    - HTTPError: If there are issues accessing the GitHub API or downloading files.
    """
    import os
    import subprocess
    import datetime
    import requests
    import pyperclip

    if extensions is None:
        extensions = []

    if clone:
        master = get_master_folder()
        repo_name = git_url.split('/')[-1].replace('.git', '')
        clone_dir = os.path.join(master, 'local_cloned', repo_name)
        subprocess.run(['git', 'clone', git_url, clone_dir], check=True)
        files = get_files_from_path(clone_dir, extensions)

        if not files:
            raise Exception("No matching files found in cloned repository.")

        content = extract_content(
            files,
            output_file=None if clipboard_only else os.path.join(
                master, 'extractions', f'{repo_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            ),
            clipboard_only=clipboard_only
        )
        
        if content:
            message = f"""
=== REPOSITORY EXTRACTION COMPLETE ===
Repository: {git_url}
File types: {extensions if extensions else 'All files'}
Number of files found: {content.count('---- ')}
=== NO NEED TO EXTRACT AGAIN ===

"""
            content = message + content
            
        return content

    else:
        slug = git_url.rstrip('/').replace('.git', '').split('/')[-2:]
        api_url = f"https://api.github.com/repos/{slug[0]}/{slug[1]}/contents"

        response = requests.get(api_url)
        response.raise_for_status()
        files = response.json()

        content = ""
        for file in files:
            if file.get('type') == 'file' and (not extensions or any(file['name'].endswith(ext) for ext in extensions)):
                download_url = file.get('download_url')
                if download_url:
                    dl_resp = requests.get(download_url)
                    dl_resp.raise_for_status()
                    content += f'\n---- {file["name"]} ----\n\n{dl_resp.text}'

        if not content:
            raise Exception("No file content extracted from GitHub repository.")

        pyperclip.copy(content)

        if not clipboard_only:
            master = get_master_folder()
            repo_name = f"{slug[0]}_{slug[1]}"
            filename = os.path.join(master, 'extractions', f'{repo_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
            with open(filename, 'w', encoding='utf-8') as out:
                out.write(content)
                
        if content:
            message = f"""
=== REPOSITORY EXTRACTION COMPLETE ===
Repository: {git_url}
File types: {extensions if extensions else 'All files'}
Number of files found: {content.count('---- ')}
=== NO NEED TO EXTRACT AGAIN ===

"""
            content = message + content
        
        return content


@tool
def extract_content_local(directory: str, extensions: list[str] = None, clipboard_only: bool = False) -> str:
    """
    Extracts content from files in the specified directory based on the given extensions.
    
    Args:
        directory (str): Path to the directory containing files to extract.
        extensions (list[str], optional): List of file extensions to filter. Extracts all files if None.
        clipboard_only (bool, optional): If True, copies extracted content to the clipboard without saving.

    Returns:
        str: Extracted content as a single string.
    
    Example Usage:
        extract_content_local("/path/to/directory", extensions=[".txt", ".md"], clipboard_only=True)
    """
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return f"Error: Directory '{directory}' does not exist or is not accessible."

    content = f"Extracted Content from: {directory}\n\n"
    extracted_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if not extensions or file.endswith(tuple(extensions)):
                file_path = os.path.join(root, file)
                extracted_files.append(file_path)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content += f"\n---- {file_path} ----\n\n{f.read()}\n"
                except Exception as e:
                    content += f"\n---- {file_path} ----\nError reading file: {str(e)}\n"

    if not extracted_files:
        return f"No matching files found in '{directory}' for extensions: {extensions}"

    pyperclip.copy(content)

    if not clipboard_only:
        master = get_master_folder()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(master, "extractions", f"extracted_{timestamp}.txt")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write(content)
    
    if content:
        message = f"""
=== LOCAL EXTRACTION COMPLETE ===
Directory: {directory}
File types: {extensions if extensions else 'All files'}
Number of files found: {len(extracted_files)}
=== NO NEED TO EXTRACT AGAIN ===

"""
        content = message + content
        
    return content

@tool
def get_system_time(format: str = "%Y-%m-%d %H:%M:%S"):
    """ Returns the current date and time in the specified format """
    current_time = datetime.datetime.now()
    formatted_time = current_time.strftime(format)
    return formatted_time


search_tool = TavilySearchResults(search_depth="basic")


def get_files_from_path(path, extensions):
    """Retrieves files from the specified path, filtering by extensions if provided."""
    matched_files = []
    if os.path.isfile(path):
        if not extensions or path.endswith(tuple(extensions)):
            matched_files.append(path)
    else:
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if not extensions or file.endswith(tuple(extensions)):
                    matched_files.append(file_path)
    return matched_files

def get_directory_structure(path):
    """Generates a directory structure listing for the given path."""
    structure = "Directory Structure:\n"
    for root, dirs, files in os.walk(path):
        level = root.replace(path, '').count(os.sep)
        indent = ' ' * 4 * level
        structure += f'{indent}{os.path.basename(root)}/\n'
        subindent = ' ' * 4 * (level + 1)
        for file in files:
            structure += f'{subindent}{file}\n'
    return structure

def extract_content(file_paths, output_file, clipboard_only):
    """Extracts content from the specified files and saves it to an output file or clipboard only."""
    content = get_directory_structure(os.path.dirname(file_paths[0])) + "\n"
    for file in file_paths:
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                content += f'\n---- {file} ----\n\n'
                content += f.read()
        except Exception as e:
            content += f'\n---- {file} ----\n\n'
            content += f"Error reading file: {str(e)}\n"
    
    pyperclip.copy(content)
    
    if not clipboard_only and output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write(content)
    
    return content