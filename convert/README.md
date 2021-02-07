## ROS Convert Gitlab-Runner

The `GITLAB_TOKEN` is a private user access token with permission to:
- read_api
- read_repo

When building the Gitlab-Runner from Docker, it is baked into the container, so that it cannot be accessed from within a project scope:

```
export GITLAB_TOKEN="<READ-API AND READ-REPO TOKEN>"
docker build --tag convert:1.0 --build-arg GITLAB_TOKEN .
```

Although there should be no access to this credential possible by manipulating a projects GitLab issues or XML files, it is recommended to create single-purpose service accounts that are scoped to each one project only.

