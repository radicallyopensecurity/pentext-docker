# quickscope2off

Convert quickscope into a quotation.

## Build

```sh
docker build -t quickscope .
```

Run with:

```sh
docker run \
  -e PROJECT_ACCESS_TOKEN="<your-gitlab-access-token>"
  -e CI_PROJECT_URL="https://git.radicallyopensecurity.com/<your-namespace>/<your-project>" \
  -e CI_PROJECT_ID="<your-gitlab-project-id>" \
  -e CI_SERVER_URL="https://git.radicallyopensecurity.com/" \
  --name convert \
  --rm \
  convert
```

## Development

Create an `.env` file:

```sh
PROJECT_ACCESS_TOKEN="<your-gitlab-access-token>"
COOKIE="_eyed_p_session=<your-eyedp-session-id>;"
```

```sh
docker run \
  --env-file ./.env
  -e CI_PROJECT_URL="https://git.radicallyopensecurity.com/<your-namespace>/<your-project>" \
  -e CI_PROJECT_ID="<your-gitlab-project-id>" \
  -e CI_SERVER_URL="https://git.radicallyopensecurity.com/" \
  --name convert \
  --rm \
  convert
```

## Test

Make sure submodules are loaded and up to date:

```sh
git submodule update --init
git submodule update
```

Make sure image is built:

```sh
docker build -t quickscope .
```

```sh
./integration.sh
```

This will:

- Create a copy of the `PenText` submodule which contains a sample quickscope report.
- Perform the conversion
- Compare the diff after conversion, with the currently committed diff
- Report differences

It will output:

- ./integration/new.diff => The diff after conversion
- ./integration/integration.diff => Diff between new diff and currently committed diff
