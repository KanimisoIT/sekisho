<#
関所の一度きりの準備(かにみその一押し)。篝が会話の中で書いた台本。

  初回:              1_setup.cmd(= sekisho-setup.ps1 -Bootstrap)
  新しいアプリのたび: 2_add_repo.cmd(= sekisho-setup.ps1 -Repo KanimisoIT/<名前>)

やること
  1. GitHub にこの台本の間だけログインする(ブラウザで承認)。PC の Git の資格情報には何も書かない
  2. 初回: 関所の本体 KanimisoIT/sekisho(公開)と 書庫の検査 KanimisoIT/sekisho-shoko(非公開)を作って上げる
     アプリ: 呼び出しの手順 .github/workflows/sekisho-call.yml を置く(AI の鍵では置けないため)
  3. 置けたリポジトリにだけ守りを掛ける: main はルールセットで「PR だけ・必須の検査が緑のときだけ・消せない・抜け道の人なし」。
     自動の取り込みを許し、取り込んだ枝は自動で消す
  4. 最後に必ずログアウトする(PC に管理の鍵を残さない)
#>
param(
    [string]$Repo,
    [switch]$Bootstrap
)
$ErrorActionPreference = 'Continue'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Body = Split-Path -Parent $Here
$Bundle = Split-Path -Parent $Body
$Owner = 'KanimisoIT'
$CallerPath = '.github/workflows/sekisho-call.yml'
$script:Failed = @()

# AI 用の鍵(GH_TOKEN など)がこのプロセスに見えていると、gh はログインもログアウトも断る。
# 消すのはこのプロセスの中だけで、利用者の環境変数はそのまま残る。
foreach ($v in 'GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN', 'GH_HOST') {
    Remove-Item "Env:$v" -ErrorAction SilentlyContinue
}
# この台本の git は gh を資格の係にする。Windows の資格情報(Git Credential Manager)には何も書かない。
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'credential.https://github.com.helper'
$env:GIT_CONFIG_VALUE_0 = '!gh auth git-credential'

function Say($m) { Write-Host "[関所] $m" }

function Need($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Say "$cmd が無い。$hint"; exit 1 }
}

function Invoke-Gh {
    $out = & gh @args
    if ($LASTEXITCODE -ne 0) { return $null }
    return $out
}

function Get-Rulesets($full) {
    $raw = Invoke-Gh api "repos/$full/rulesets"
    if (-not $raw) { return @() }
    $list = ConvertFrom-Json ($raw | Out-String)
    return @($list | ForEach-Object { $_ })
}

function Protect($full, $check) {
    Say "$full に守りを掛ける(必須の検査: $check)"
    $null = Invoke-Gh api -X PATCH "repos/$full" -F allow_auto_merge=true -F delete_branch_on_merge=true -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false
    if ($LASTEXITCODE -ne 0) { Say '  設定を変えられなかった'; $script:Failed += "$full の設定" }
    $json = (Get-Content (Join-Path $Here 'ruleset.json') -Raw -Encoding UTF8).Replace('__CHECK__', $check)
    $tmp = (New-TemporaryFile).FullName
    [IO.File]::WriteAllText($tmp, $json, (New-Object Text.UTF8Encoding $false))
    $found = @(Get-Rulesets $full | Where-Object { $_.name -eq 'sekisho' })
    if ($found.Count -gt 0) { $null = Invoke-Gh api -X PUT "repos/$full/rulesets/$($found[0].id)" --input $tmp }
    else { $null = Invoke-Gh api -X POST "repos/$full/rulesets" --input $tmp }
    if ($LASTEXITCODE -ne 0) {
        Say '  ルールセットを掛けられなかった。非公開のリポジトリなら GitHub Pro が要る。Pro にしてから押し直す'
        $script:Failed += "$full のルールセット"
    } else { Say '  ルールセットを掛けた' }
    Remove-Item $tmp -ErrorAction SilentlyContinue
}

function PushNew($dir, $name, $visibility) {
    if (-not (Test-Path $dir)) { Say "$dir が無い(一式の展開の形を確かめる)"; $script:Failed += "$name の作成"; return $false }
    Push-Location $dir -ErrorAction Stop
    try {
        if (-not (Test-Path .git)) { git init -q -b main }
        git -c core.autocrlf=false add -A
        git -c "user.name=$Owner" -c "user.email=$Owner@users.noreply.github.com" commit -q -m "$name first version" 2>&1 | Out-Null
        $null = Invoke-Gh repo create "$Owner/$name" "--$visibility" --source . --push
        if ($LASTEXITCODE -ne 0) { Say "$Owner/$name を作れなかった(もう有るなら飛ばしてよい)"; $script:Failed += "$name の作成"; return $false }
        Say "$Owner/$name を作って上げた($visibility)"
        return $true
    } finally { Pop-Location }
}

function PutCaller($full) {
    $text = Get-Content (Join-Path $Body 'caller\sekisho-call.yml') -Raw -Encoding UTF8
    $b64 = [Convert]::ToBase64String((New-Object Text.UTF8Encoding $false).GetBytes($text))
    $def = "$(Invoke-Gh api "repos/$full" --jq .default_branch)".Trim()
    if (-not $def) { Say "$full が見つからない(名前を確かめる)"; $script:Failed += "$full の呼び出し"; return $false }
    $cur = Invoke-Gh api "repos/$full/contents/$($CallerPath)?ref=$def" --jq .content
    if ($cur) {
        $now = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((($cur | Out-String) -replace '\s', '')))
        if ($now -eq $text) { Say "$full の呼び出しはもう置いてある"; return $true }
    }
    $guarded = @(Get-Rulesets $full | Where-Object { $_.name -eq 'sekisho' }).Count -gt 0
    if (-not $guarded) {
        $callArgs = @('api', '-X', 'PUT', "repos/$full/contents/$CallerPath", '-f', 'message=sekisho: caller', '-f', "content=$b64", '-f', "branch=$def")
        $old = Invoke-Gh api "repos/$full/contents/$($CallerPath)?ref=$def" --jq .sha
        if ($old) { $callArgs += @('-f', "sha=$("$old".Trim())") }
        $null = Invoke-Gh @callArgs
        if ($LASTEXITCODE -ne 0) { Say '呼び出しの手順を置けなかった'; $script:Failed += "$full の呼び出し"; return $false }
        Say "$full に呼び出しの手順を置いた"
        return $true
    }
    # 守りが掛かっている: 枝に置いて PR を出し、関所が緑になったら自動で取り込ませる
    $branch = 'sekisho-caller-' + (Get-Date -Format 'yyyyMMddHHmm')
    $baseSha = "$(Invoke-Gh api "repos/$full/git/ref/heads/$def" --jq .object.sha)".Trim()
    $null = Invoke-Gh api -X POST "repos/$full/git/refs" -f "ref=refs/heads/$branch" -f "sha=$baseSha"
    $callArgs = @('api', '-X', 'PUT', "repos/$full/contents/$CallerPath", '-f', 'message=sekisho: caller', '-f', "content=$b64", '-f', "branch=$branch")
    $old = Invoke-Gh api "repos/$full/contents/$($CallerPath)?ref=$branch" --jq .sha
    if ($old) { $callArgs += @('-f', "sha=$("$old".Trim())") }
    $null = Invoke-Gh @callArgs
    $null = Invoke-Gh pr create -R $full --head $branch --base $def --title 'sekisho: caller' --body 'sekisho caller'
    $null = Invoke-Gh pr merge $branch -R $full --auto --squash
    if ($LASTEXITCODE -ne 0) { Say '呼び出しの PR を出せなかった'; $script:Failed += "$full の呼び出し"; return $false }
    Say "$full に呼び出しの PR を出した(関所が緑になれば自動で入る)"
    return $true
}

# gh(GitHub の公式の道具)が無ければ winget で入れる。同意や許可の確認は、かにみそが読んで答える。
if (-not (Get-Command gh -ErrorAction SilentlyContinue) -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Say 'gh が無いので winget で入れる。「同意しますか」と出たら読んで Y、許可の確認が出たら「はい」'
    winget install --id GitHub.cli --exact --source winget
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
Need 'gh' 'winget install GitHub.cli で入れてから押し直す'
Need 'git' 'winget install Git.Git で入れてから押し直す'
$ghv = [version](((gh --version) -join ' ') -replace '.*gh version (\d+\.\d+\.\d+).*', '$1')
if ($ghv -lt [version]'2.40.0') { Say 'gh が古い。winget upgrade GitHub.cli をしてから押し直す'; exit 1 }
if (-not $Bootstrap -and -not $Repo) { Say '-Bootstrap か -Repo KanimisoIT/<名前> を付けて押す'; exit 1 }
if ($Repo) {
    $Repo = ($Repo.Trim() -replace '^https?://github\.com/', '' -replace '\.git$', '').Trim('/')
    if ($Repo -notmatch '/') { $Repo = "$Owner/$Repo" }
    if ($Repo -notmatch '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$') { Say "名前の形が違う: $Repo"; exit 1 }
}

Say 'GitHub にこの台本の間だけログインする。'
Say '8桁の符号が出る(写しは自動で取られる)。Enter でブラウザが開くので、Ctrl+V で貼って Continue → Authorize を押す。'
gh auth login --hostname github.com --web --clipboard --git-protocol https --scopes 'repo,workflow'
if ($LASTEXITCODE -ne 0) { Say 'ログインできなかった'; exit 1 }
$login = "$(Invoke-Gh api user --jq .login)".Trim()
try {
    if ($login -ne $Owner) {
        Say "承認したのは「$login」だった。ブラウザで $Owner に入り直してから押し直す"
        $script:Failed += 'ログインの持ち主'
    } else {
        if ($Bootstrap) {
            if (PushNew (Join-Path $Bundle 'sekisho') 'sekisho' 'public') { Protect "$Owner/sekisho" 'self-test' }
            if (PushNew (Join-Path $Bundle 'sekisho-shoko') 'sekisho-shoko' 'private') { Protect "$Owner/sekisho-shoko" 'self-test' }
        }
        if ($Repo) {
            if (PutCaller $Repo) { Protect $Repo 'sekisho / verdict' }
        }
    }
} finally {
    Say 'ログアウトする'
    if ($login) { gh auth logout --hostname github.com --user $login 2>&1 | Out-Null }
    else { gh auth logout --hostname github.com 2>&1 | Out-Null }
    $left = (gh auth status 2>&1 | Out-String)
    if ($left -match 'not logged into any') { Say 'ログインは残っていない' }
    else { Say '注意: まだログインが残っている。gh auth status で見る' }
    Say 'この台本のログインの鍵を GitHub 側でも消すなら: https://github.com/settings/applications の GitHub CLI → Revoke'
}
if ($script:Failed.Count -gt 0) { Say ('済んでいない所: ' + ($script:Failed -join '、')); exit 1 }
Say '済んだ'
