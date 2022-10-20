# convert

Pre-process `.xml` files, performing conversions and formatting where necessary.

## Usage

Build the image:

```sh
docker build --tag convert .
```

To run the image you need a GitLab token.

The `GITLAB_TOKEN` is a private user access token with permission to:

- `read_api`
- `read_repo`

```sh
docker run \
  -e "PROJECT_ACCESS_TOKEN={{GITLAB_TOKEN}}" \
  -e "CI_PROJECT_URL={{YOUR_GITLAB_PROJECT_URL}}" \
  -e "CI_PROJECT_ID={{YOUR_GITLAB_PROJECT_ID}}" \
  -e "CI_SERVER_URL={{YOUR_GITLAB_URL}} \
  --name "convert" \
  --rm \
  convert
```
