# Connect images you already have to Antenna

Antenna reads capture images from S3-compatible object storage. If your images already sit in a folder on your computer, on a network drive, or in a cloud drive, you do not need to copy them into a bucket first. A small program, [rclone](https://rclone.org/), can present any folder as a read-only S3 endpoint, and Antenna treats it like any other storage source: it lists the files, groups them into sessions, and hands image URLs to the processing services. Nothing is written back to your folder.

Contents:

1. [When to use this, and when to import instead](#when-to-use-this)
2. [How Antenna sees your folder](#how-antenna-sees-your-folder)
3. [With or without access keys](#with-or-without-access-keys)
4. [Local Antenna, files on the same computer](#local-antenna-files-on-the-same-computer)
5. [Hosted Antenna, files on your computer, through a tunnel](#hosted-antenna-files-on-your-computer-through-a-tunnel)
6. [Network drives and cloud drives](#network-drives-and-cloud-drives)
7. [Troubleshooting](#troubleshooting)

Recipes marked **tested** were run against Antenna's own test stack in September 2026 with rclone 1.75.1. Recipes marked **from the vendor docs** need an account, OAuth, or a specific operating system and were not run by us; please open an issue if one needs adjusting. `rclone serve s3` is labelled experimental by the rclone project; it has behaved well in our tests, but pin the rclone version you deploy with.

## When to use this

Use a gateway when the files are already organised where they live and you do not want a second copy: an archive on a lab NAS, a shared Google Drive, a field laptop. Antenna reads the images in place every time it needs them (sync, processing, crop generation, thumbnails), so the location must stay reachable while jobs run.

Import instead (upload into Antenna's own storage) when you bring in new material from SD cards and want Antenna to organise it, remove duplicates, and keep it available after the laptop is closed. Import tooling is tracked separately.

## How Antenna sees your folder

`rclone serve s3 <folder>` turns each **top-level sub-folder** of `<folder>` into a bucket, and every file below that into an object whose key is its relative path. Files directly in `<folder>` are ignored. So to expose a folder called `captures`, serve its **parent**:

```
photos/                           <- serve this
└── captures/                     <- bucket "captures"
    ├── vermont-trap-01/          <- deployment sub-directory
    │   └── 2024-06-10/
    │       └── 20240610210111-snapshot.jpg
    └── cyprus site 2/
        └── 2024-07-01/...
```

The storage source form in Antenna maps onto that:

| Field | Value | Notes |
|---|---|---|
| Endpoint URL | `http://<gateway-host>:9111` | where Antenna's containers reach the gateway |
| Bucket | `captures` | the top-level sub-folder name |
| Prefix | empty, or a sub-folder | narrows what every deployment on this source can see |
| Access key, Secret key | any non-empty text without access keys; the real pair with access keys | Antenna always signs its requests |
| Public base URL | `http://<gateway-host>:9111/captures/` | Leave **empty** to make Antenna hand out presigned URLs instead (needed with access keys) |

Each deployment then points at a sub-directory (`vermont-trap-01`, `cyprus site 2`; spaces are fine) and "Sync captures" imports the files. Timestamps are read from the filenames, as with any other source; `YYYYMMDDHHMMSS` anywhere in the name is the safest form.

Files that are not images (`.txt`, `.DS_Store`, RAW formats) are listed by the gateway but skipped by Antenna's file-type filter; the sync log reports how many were skipped.

## With or without access keys

rclone serves anonymously unless you pass `--auth-key`. Both modes work with Antenna; pick by who can reach the gateway.

**Without access keys** (`--read-only` only). Anyone who can reach the port can list and download every file. Fine on your own computer or a private network. In Antenna, put any text in the key fields and set the Public base URL, so browsers and processing services fetch plain URLs. **Tested.**

**With access keys** (`--auth-key ACCESSKEY,SECRETKEY`). Every request must be signed. Give Antenna the same pair and leave the Public base URL **empty**: Antenna then generates a presigned URL for each image (valid for 7 days) and hands that to browsers and processing services. Required whenever the gateway is reachable from the internet. **Tested:** plain URLs are refused (`400 UnsupportedAlgorithm`), presigned URLs work for keys with spaces and accents, a URL with a changed signature or a different secret is refused (`403 SignatureDoesNotMatch`), an expired URL is refused (`400 AccessDenied`), and a presigned URL cannot be reused for a different file. Leave the region empty or use `us-east-1`; rclone does not check it.

Generate a key pair however you like, for example `openssl rand -hex 16` twice. A presigned URL is a bearer token for that one file until it expires, so treat shared links accordingly.

## Local Antenna, files on the same computer

### Variant A: run rclone next to your files (any OS, no compose change)

[Install rclone](https://rclone.org/install/) (single binary for Windows, macOS, Linux). Open a terminal in the folder that **contains** your capture folder and run:

```
rclone serve s3 . --addr :9111 --read-only --dir-cache-time 30s
```

**Tested** on Linux with the release binary. On Windows use the same command from PowerShell or `cmd`; paths such as `C:\photos`, `C:/photos` or a UNC path `\\server\share\photos` are accepted in place of `.` (**from the rclone docs**).

Leave it running. In Antenna create the storage source with:

- Endpoint URL: `http://host.docker.internal:9111`
- Bucket: your folder's name
- Public base URL: `http://host.docker.internal:9111/<folder>/`

`host.docker.internal` is how the Antenna containers reach a program on your computer. Docker Desktop (macOS, Windows) resolves it inside containers and also adds it to your computer's hosts file, so the same URL works in your browser. On Linux add one line to `/etc/hosts`, the same way the README asks you to add `minio` and `django`:

```
127.0.0.1 host.docker.internal
```

**Tested:** two deployments (1,500 and 1,681 images, one sub-directory with a space, one filename with an accent) synced in under 2 s each, sessions were grouped, and the processing service fetched and processed an image through this URL.

### Variant B: mount a folder into the Antenna stack (compose profile)

Set the folder once in the `.env` file next to `docker-compose.yml` (create the file if it does not exist; it is ignored by git), then start the stack with the `local-files` profile:

```
# .env
ANTENNA_LOCAL_FILES_DIR=/home/me/photos
```

```
docker compose --profile local-files up -d
```

This starts a `local-files` service (`rclone/rclone`) that serves `ANTENNA_LOCAL_FILES_DIR` read-only on port 9111: inside the stack as `http://local-files:9111`, on your computer as `http://localhost:9111`. Antenna stores one public URL per source that both your browser and the processing services must be able to open, so add the alias to `/etc/hosts` (as for `minio`):

```
127.0.0.1 local-files
```

Storage source values: Endpoint `http://local-files:9111`, Bucket = sub-folder name, Public base URL `http://local-files:9111/<sub-folder>/`.

The folder cannot change while the stack runs (it is a bind mount); edit `.env` and restart the `local-files` service. Point the variable at the *parent* of your capture folders so that each of them appears as a bucket.

Platform notes (**from the Docker docs**): on Windows write the path with forward slashes, `C:/Users/me/photos`; from a WSL shell use `/mnt/c/Users/me/photos`, or better a folder inside the WSL filesystem, which is much faster. On macOS the first mount of a folder under Documents, Desktop or Downloads triggers a permission prompt; grant it or the mount is empty. On Linux the files must be readable by the container's user; world-readable files always work.

### New files

rclone caches directory listings for `--dir-cache-time` (default 5 minutes; the recipes above use 30 s). A file added to the folder appears in the next sync after that delay. **Tested:** with the default, a new file took about 5 minutes to appear; with `--dir-cache-time 10s`, about 10 s.

## Hosted Antenna, files on your computer, through a tunnel

If Antenna runs on a server (for example the hosted instance) and the images are on your computer, expose the gateway through an HTTPS tunnel. Always use access keys here: the tunnel URL is public.

Start rclone with keys:

```
rclone serve s3 . --addr 127.0.0.1:9111 --read-only --auth-key ACCESSKEY,SECRETKEY --dir-cache-time 30s
```

Then choose a tunnel.

### Cloudflare Tunnel

Quick tunnel, no account, throwaway URL (**tested**):

```
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:9111
```

After a few seconds the log prints a URL like `https://random-words.trycloudflare.com`. In Antenna: Endpoint URL = that URL, Bucket = folder name, keys = the pair above, Public base URL **empty**. **Tested:** signed listing, presigned downloads (0.2 to 0.5 s per image through the tunnel), refused unsigned and tampered requests, no interstitial page, images arrive as `image/jpeg`. Quick tunnels have no uptime guarantee and a new hostname on every start, so re-enter the endpoint when you restart.

Persistent tunnel with a Cloudflare account and your own hostname (**from the Cloudflare docs**):

```
cloudflared tunnel login
cloudflared tunnel create antenna-images
cloudflared tunnel route dns antenna-images images.example.org
cloudflared tunnel run --url http://127.0.0.1:9111 antenna-images
```

### Tailscale

**From the Tailscale docs**, not run by us. Funnel publishes the port on the internet over HTTPS:

```
tailscale funnel --bg 9111        # https://<machine>.<tailnet>.ts.net
tailscale funnel status
tailscale funnel reset            # turn off
```

Funnel must be enabled for your tailnet (a `funnel` node attribute in the ACL policy; the CLI shows an enable link on first use), and it only serves on ports 443, 8443 and 10000 (`--https=8443` to pick one). If the Antenna server is itself on your tailnet, prefer `tailscale serve --bg 9111`, which is reachable only inside the tailnet and never public.

### What to expect

Every image fetch, including crop generation and thumbnails, goes out through your uplink, and the computer must stay on for the whole job. This suits browsing and trial runs of a few thousand images. For large runs, importing the images into Antenna's storage is the better tool.

## Network drives and cloud drives

`rclone serve s3` can front anything rclone can read, not just local folders. Configure a *remote* once, then serve it.

### Windows network drive (SMB share)

Simplest, **from the rclone docs**: run rclone on the Windows machine and give it the UNC path directly (a mapped drive letter also works from an interactive session, but not from a service or scheduled task):

```
rclone serve s3 \\server\share\photos --addr 127.0.0.1:9111 --read-only --auth-key ACCESSKEY,SECRETKEY
```

Quote the path if it contains spaces. Long paths are handled automatically.

From any OS, through rclone's SMB backend (**tested** on Linux against a Samba server):

```
rclone config create nas smb host=nas.local user=smbuser pass="$(rclone obscure 'the-password')"
rclone lsd nas:                     # lists the shares; find the one holding your folders
rclone serve s3 nas:photos --addr :9111 --read-only --dir-cache-time 30s
```

Buckets are the top-level folders inside the share path you serve, so serve the folder that contains `captures`, not `captures` itself. **Tested:** 3,185 files listed in 0.3 s over a loopback SMB connection; sizes and modification times come through; there is no checksum from SMB, so Antenna stores none. Expect slower listings over a real network (one directory call per folder).

### Google Drive

**From the rclone docs**, not run by us (needs a browser sign-in):

```
rclone config          # n) New remote, name: gdrive, Storage: drive
                       # client_id / client_secret: create your own in Google Cloud Console
                       # scope: 2 (read-only)
                       # Use web browser to authenticate: y
rclone serve s3 gdrive:Captures --addr :9111 --read-only --dir-cache-time 5m
```

Notes: create your own OAuth client id; rclone's shared default is heavily rate limited. The first listing of a large folder can take minutes because of Drive API rate limits (`--fast-list` reduces calls at the cost of memory). Drive already stores MD5 checksums, so the default `--etag-hash MD5` costs nothing here. For folders shared with you, add `--drive-shared-with-me`; for a Shared Drive, set `team_drive` during `rclone config`. Google Photos is a different remote and serves downscaled images: not suitable.

Other rclone backends (Dropbox, OneDrive, SFTP, Nextcloud, another S3 bucket) work the same way: `rclone config`, then `rclone serve s3 <remote>:<path>`.

## Troubleshooting

- **Every image URL returns 404, but "Test connection" succeeded.** On Antenna versions before October 2026 a public base URL without a trailing `/` lost its last path segment; edit the source and add the slash. Current versions build the URL correctly either way.
- **"0 files imported" after syncing a full folder.** Read the sync log's skipped-files line: the files are not in a supported image format, or the deployment sub-directory does not match the folder name (case and spaces matter).
- **`S3 API Requests must be made to API port`** during the connection test: the port you entered belongs to something else (for example MinIO's console). Check rclone's `--addr`.
- **The processing service cannot download images but the browser can** (or the reverse): the two resolve the hostname differently. Use one hostname both can reach (`host.docker.internal` or an `/etc/hosts` alias), never `localhost`.
- **`400 UnsupportedAlgorithm` on image URLs.** rclone runs with `--auth-key` but the storage source has a Public base URL. Clear the Public base URL so Antenna uses presigned URLs, or run rclone without keys on a private network.
- **`403 SignatureDoesNotMatch` or `InvalidAccessKeyId`.** The keys in Antenna differ from rclone's `--auth-key` pair.
- **Writes fail with `500 InternalError`.** Expected in `--read-only` mode. Antenna never writes to sources; this only appears if something else tries.
- **First sync of a huge folder is slow.** rclone reads each file once per listing to compute MD5 checksums; add `--etag-hash ""` to skip that (Antenna then stores no checksum for these captures). Listing 100,000 files took about 50 s in our test; a single deployment's sub-directory lists in milliseconds.
