from setuptools import setup, find_packages
from pathlib import Path

# -------------------------------
# Long description from README.md
# -------------------------------
this_directory = Path(__file__).parent
readme_file = this_directory / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# -------------------------------
# Load dependencies dynamically
# -------------------------------
def read_requirements(file_path="requirements.txt"):
    """Read dependencies from requirements.txt (ignore comments & blank lines)."""
    requirements = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                requirements.append(line)
    return requirements


install_requires = read_requirements()

# -------------------------------
# Setup configuration
# -------------------------------
setup(
    name="intelligent-fraud-detection-chatbot",
    version="0.1.0",
    author="Pruthviraj Rathod",
    author_email="prithvirathod29884@gmail.com",
    description=(
        "AI-powered insurance fraud detection chatbot integrating FastAPI, LangChain, "
        "and AWS (Lambda, SageMaker, RDS, S3)."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/prithvi429/intelligent-fraud-detection-chatbot",
    license="MIT",
    packages=find_packages(include=["src*", "chatbot*", "ml*"]),
    include_package_data=True,
    package_data={"": ["*.pkl", "*.md"]},
    zip_safe=False,
    python_requires=">=3.10",
    install_requires=install_requires,
    extras_require={
        "dev": [
            "pytest==7.4.3",
            "pytest-mock==3.12.1",
            "black==23.11.0",
            "flake8==6.1.0",
            "coverage==7.3.2",
            "pre-commit==3.6.0",
        ],
        "ml": [
            "tensorflow==2.13.0",
        ],
    },
    entry_points={
        "console_scripts": [
            # Run FastAPI app
            "fraud-api=src.main:run_api",
            # Train model
            "fraud-train=ml.train:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Documentation": "https://github.com/prithvi429/intelligent-fraud-detection-chatbot/wiki",
        "Bug Tracker": "https://github.com/prithvi429/intelligent-fraud-detection-chatbot/issues",
    },
)
