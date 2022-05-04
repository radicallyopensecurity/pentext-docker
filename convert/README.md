# convert

Pre-process `.xml` files, performing conversions and formatting where necessary.

## Usage

To build the GitLab runner you need a token from GitLab.

The `GITLAB_TOKEN` is a private user access token with permission to:

- `read_api`
- `read_repo`

When building the Gitlab runner from Docker, it's baked into the container, so that it can't be accessed from within a project scope:

```sh
export GITLAB_TOKEN="<READ-API AND READ-REPO TOKEN>"
docker build --tag convert:1.0 --build-arg GITLAB_TOKEN .
```

Although there should be no access to this credential possible by manipulating a projects GitLab issues or `xml` files, it's recommended to create single-purpose service accounts that are scoped to each one project only.