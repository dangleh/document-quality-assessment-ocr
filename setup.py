from setuptools import setup, find_packages

# Read the contents of your README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read the requirements from requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as f:
    # Filter out testing/dev dependencies and comments
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith(("#", "pytest", "black", "flake8", "mypy", "isort"))
    ]

setup(
    name="document_assessor",
    version="1.0.0",
    author="Dang Le",  
    author_email="lehaidang2601@gmail.com",  
    description="A library to assess the quality of documents for OCR processing.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dangleh/document-quality-assessment-ocr", 
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Image Processing",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
)