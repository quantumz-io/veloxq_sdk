# VeloxQ SDK: Documentation & Usage Guide

This project provides a configurable Python API to interact with the VeloxQ platform, designed to provide users with a **powerful**, **robust** and **user-friendly** interface to upload and solve complex optimization problems using an extensive list of physics-inspired and metaheuristic algorithms.

The primary components of the API include Jobs, Solvers, and Problems:
1. **Jobs**: A 'job' in this context refers to a specific execution of a solver on a problem.
2. **Solvers**: The solvers are the algorithms used to solve the optimization problems executed on a specific backend. The solvers can be configured with a wide array of parameters that help in fine-tuning the solver's behavior, offering a high degree of customization for different types of optimization problems.
3. **Problems**: Problems are the specific computational task at hand, composed by multiple files in various formats that contains the problem data.

This docs covers usage from initial setup through job submission and retrieval.

## Table of Contents

- [Configuration](configuration.md#configuration)
  - [Environment Variables](configuration.md#environment-variables)
  - [File-Based Configuration](configuration.md#file-based-configuration)
  - [Generating a Default Configuration](configuration.md#generating-a-default-configuration)
  - [Live Updates to Configuration](configuration.md#live-updates-to-configuration)
- [Selecting Solvers & Backends](solvers-and-backends.md#selecting-solvers--backends)
  - [Default Solver: VeloxQSolver](solvers-and-backends.md#1-default-solver-veloxqsolver)
  - [Setting Solver Parameters](solvers-and-backends.md#2-setting-solver-parameters)
  - [SBM Solver](solvers-and-backends.md#3-sbm-solver)
  - [Backend Options](solvers-and-backends.md#4-backend-options)
- [Defining Problems & Files](problems-and-files.md#defining-problems--files)
  - [Managing Problems](problems-and-files.md#1-managing-problems)
  - [Creating Files from Different Sources](problems-and-files.md#2-creating-files-from-different-sources)
  - [Uploading & Overwriting Files](problems-and-files.md#3-uploading--overwriting-files)
  - [Associating with Problems](problems-and-files.md#4-associating-with-problems)
  - [Downloading Files](problems-and-files.md#5-downloading-files)
- [Submitting Jobs](jobs.md#1-submitting-jobs)
- [Retrieving & Managing Jobs](jobs.md#2-retrieving--managing-jobs)
  - [Waiting for Completion](jobs.md#21-waiting-for-completion)
  - [Listing Jobs](jobs.md#22-listing-jobs)
  - [Retrieving Job by ID](jobs.md#23-retrieving-job-by-id)
  - [Getting Job Logs](jobs.md#24-getting-job-logs)
- [Accessing Results](results.md#accessing-results)
  - [Direct Access via VeloxSampleSet](results.md#1-direct-access-via-veloxsampleset)
  - [Downloading the Result File](results.md#2-downloading-the-result-file)
