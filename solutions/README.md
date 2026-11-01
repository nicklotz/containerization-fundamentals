# Solutions

This folder holds every file that you create or change in the labs, as it is at the end of each lab.

- `solutions/labNN/` holds the files of Lab NN.
- The path below `labNN/` is the path below your home folder. For example, `solutions/lab02/bagtrack/bag-api/Dockerfile` is `~/bagtrack/bag-api/Dockerfile` at the end of Lab 02.
- A lab that creates or changes no files has no folder.

To compare one of your files with the solution, use `diff`:

```bash
diff ~/bagtrack/bag-api/Dockerfile ~/containerization-fundamentals/solutions/lab02/bagtrack/bag-api/Dockerfile
```

No output means that the two files are the same.
