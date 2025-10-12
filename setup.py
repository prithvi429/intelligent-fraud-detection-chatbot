from setuptools import setup, find_packages
from pathlib import Path

# -------------------------------
# Long Description
# -------------------------------
this_directory = Path(__file__).parent
readme_file = this_directory / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# -------------------------------
# Load Dependencies
# -------------------------------
def read_requirements(file_path="requirements.txt"):
    """Read dependencies from requirements.txt (ignore comments & blank lines)."""
    requirements = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    requirements.append(line)
    except FileNotFoundError:
        print("⚠️ requirements.txt not found; using defaults.")
    return requirements


install_requires = read_requirements()

# -------------------------------
# Package Configuration
# -------------------------------
setup(
    name="intelligent-fraud-detection-chatbot",
    version="0.2.0",
    author="Pruthviraj Rathod",
    author_email="prithvirathod29884@gmail.com",
    description="AI-powered insurance fraud detection chatbot integrating FastAPI, LangChain, and AWS (Lambda, SageMaker, RDS, S3).",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/prithvi429/intelligent-fraud-detection-chatbot",
    license="MIT",
    packages=find_packages(include=["src*", "chatbot*", "ml*", "tests*"]),
    include_package_data=True,
    package_data={"": ["*.pkl", "*.md", "*.json"]},
    zip_safe=False,
    python_requires=">=3.10",
    install_requires=install_requires,
    extras_require={
        "dev": [
            "pytest>=8.3.3",
            "pytest-mock>=3.14.0",
            "black>=24.8.0",
            "flake8>=7.0.0",
            "coverage>=7.6.0",
            "pre-commit>=3.8.0",
        ],
        "ml": [
            "tensorflow>=2.13.0",
            "torch>=2.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "fraud-api=src.main:run_api",     # Run FastAPI app
            "fraud-train=ml.train:main",      # Train ML model
            "fraud-chat=chatbot.agent:run_agent",  # Run chatbot agent REPL
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "Topic :: Software Development :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Documentation": "https://github.com/prithvi429/intelligent-fraud-detection-chatbot/wiki",
        "Bug Tracker": "https://github.com/prithvi429/intelligent-fraud-detection-chatbot/issues",
        "Changelog": "https://github.com/prithvi429/intelligent-fraud-detection-chatbot/releases",
    },
)
