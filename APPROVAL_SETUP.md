# Instagram Post Approval Setup

This guide explains how to configure the approval workflow for Instagram posts.

## How It Works

The workflow is split into two jobs:

1. **Generate Job** (automatic):
   - Runs on schedule or manual trigger
   - Generates posts using AI
   - Uploads posts as artifacts
   - Commits metadata to repository

2. **Post to Instagram Job** (requires approval):
   - Waits for manual approval
   - Downloads approved posts
   - Posts to Instagram

## Setup Steps

### 1. Create GitHub Environment

1. Go to your repository on GitHub
2. Click **Settings** → **Environments**
3. Click **New environment**
4. Name it: `instagram-production`
5. Click **Configure environment**

### 2. Configure Protection Rules

On the environment configuration page:

1. Check ✅ **Required reviewers**
2. Add yourself (or team members) as reviewers
3. (Optional) Set **Wait timer** to 0 minutes (or add a delay if you want)
4. Click **Save protection rules**

### 3. Add Instagram Secrets

Go to **Settings** → **Secrets and variables** → **Actions**

Add these secrets:
- `GEMINI_API_KEY` - Your Gemini API key (already added)
- `INSTAGRAM_USERNAME` - Your Instagram username
- `INSTAGRAM_PASSWORD` - Your Instagram password (or app-specific password)

### 4. (Optional) Add Variables

Go to **Settings** → **Secrets and variables** → **Actions** → **Variables** tab

Add:
- `INSTAGRAM_USERNAME` - Your public Instagram username (for the environment URL)

## Approval Workflow

### When Posts Are Generated:

1. The workflow runs automatically (every 6 hours) or manually
2. Posts are generated and uploaded as artifacts
3. You'll receive a notification requesting approval
4. Workflow pauses at the "post-to-instagram" job

### How to Review & Approve:

1. Go to **Actions** tab in your repository
2. Click on the running workflow
3. Click **Review deployments** button (yellow banner)
4. Download and review the artifacts:
   - Click on **generated-posts-XXX** artifact
   - Download and extract to view images
5. Make your decision:
   - ✅ Click **Approve and deploy** to post to Instagram
   - ❌ Click **Reject** to cancel posting

### Artifact Review:

The artifacts contain:
- `*.png` - Generated Instagram post images
- `posts.json` - Post metadata (titles, captions, hashtags)

Review the images and captions before approving!

## Testing the Setup

1. Manually trigger the workflow:
   ```bash
   # Via GitHub UI: Actions → Generate Instagram Posts → Run workflow
   ```

2. Wait for the "generate" job to complete

3. You should see a yellow banner: "Waiting for approval"

4. Click "Review deployments" to approve or reject

## Next Steps

- [ ] Set up GitHub Environment with protection rules
- [ ] Add Instagram credentials as secrets
- [ ] Implement Instagram posting logic (currently a TODO)
- [ ] Test the approval workflow

## Instagram Posting Implementation

The actual Instagram posting is currently a TODO. You'll need to:

1. Choose an Instagram API library (e.g., `instagrapi`, `instabot`)
2. Create a Python script to handle posting
3. Update the workflow step to call your posting script

Example libraries:
- **instagrapi**: Most reliable, actively maintained
- **instabot**: Simple but less maintained
- **Instagram Graph API**: Official but requires Business account

Let me know if you need help implementing the Instagram poster!
