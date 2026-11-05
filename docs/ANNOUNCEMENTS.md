# SOBYA Validator Recruitment — Publication Pack

**Current wording: recruiting expressions of interest for a future independent-operator testnet.** Do not say the testnet is live, applications are approved, or rewards are guaranteed. Add official contact/channel links only after the project owner confirms them.

## X post (English)

SOBYA is preparing an independent-validator testnet and inviting expressions of interest from experienced Cosmos SDK / CometBFT operators.

We are looking for operators who control their own Linux infrastructure, can maintain reliable uptime, and can provide public P2P connectivity. Validators keep their own signing keys; SOBYA will never ask for seed phrases or private keys.

This is an early operator-recruitment phase—not a live network or investment offer. Testnet tokens have no monetary value. No income, reimbursement, or token price is promised.

Read the operator preparation guide: https://github.com/snforem-cpu/sobya-chain/blob/main/docs/STAGE_THREE_OPERATOR_KIT.md

## X post (Arabic)

تستعد SOBYA لمرحلة شبكة اختبار عامة تعتمد على مدققين مستقلين، ونفتح باب إبداء الاهتمام للمشغلين ذوي الخبرة في Cosmos SDK وCometBFT.

نبحث عن مشغلين يمتلكون خوادم Linux مستقلة واتصالاً مستقراً وإمكانية فتح اتصال P2P. يحتفظ كل مدقق بمفاتيح التوقيع لديه، ولن نطلب أبداً العبارة السرية أو المفتاح الخاص.

هذه مرحلة استقطاب وتجهيز وليست شبكة حية أو عرضاً استثمارياً. رموز الاختبار لا قيمة مالية لها، ولا توجد وعود بأرباح أو تعويضات أو سعر للعملة.

دليل المشغلين: https://github.com/snforem-cpu/sobya-chain/blob/main/docs/STAGE_THREE_OPERATOR_KIT.md

## Telegram pinned message (Arabic)

**مرحباً بمهتمي تشغيل عقد SOBYA**

نستقبل حالياً طلبات إبداء الاهتمام لتشغيل عقد مستقلة ضمن شبكة اختبار مستقبلية.

الأدوار المطلوبة:
- Validator: عقدة تشارك في الإجماع.
- Seed: عقدة تساعد في اكتشاف الأقران.
- RPC / Full node: عقدة غير مدققة لتقديم الاستعلامات بعد تأمينها.

يرجى إرسال معلومات عامة فقط: اسم المشغل، وسيلة التواصل، المنطقة الجغرافية العامة، مواصفات الخادم، نظام Linux، الخبرة السابقة، والدور المطلوب. لا ترسلوا كلمات مرور أو مفاتيح أو عبارات استرداد أو ملفات keyring أو ملفات validator.

لن يبدأ تشغيل الشبكة إلا بعد اعتماد نسخة البرنامج ومعرّفي الشبكة وملف Genesis النهائي وبصمته SHA-256 وقائمة الأقران وموعد الإطلاق. لا تستخدموا chain ID أو Genesis تجريبياً من عندكم.

رموز الاختبار بلا قيمة مالية، ولا يوجد ضمان مكافآت أو تعويض تكاليف. دليل الانضمام: https://github.com/snforem-cpu/sobya-chain/blob/main/docs/STAGE_THREE_OPERATOR_KIT.md

## Operator application template

- Operator/team:
- Contact:
- Country / broad region:
- Hosting provider:
- Linux distribution/version:
- CPU / RAM / SSD:
- Expected uptime / maintenance window:
- Inbound P2P TCP available?:
- Cosmos SDK / CometBFT experience:
- Preferred role: validator / seed / RPC / full node:

Do not include credentials, account IDs, private keys, mnemonics, seed phrases, keyring archives, or validator signing files.

## FAQ

**Is SOBYA testnet live now?** No. This is preparation and recruitment only. A live-testnet announcement requires the published launch bundle and successful independent-host consensus checks.

**Do I need to send my validator key to the project?** Never. Generate and retain it locally. Only public details and the signed gentx are shared when the official ceremony begins.

**Will I earn money or guaranteed tokens?** No financial return or reimbursement is promised. Testnet tokens have no monetary value. The protocol reserve rules are documented in `sobya/TOKENOMICS.md`.

**Can I use a GitHub Actions runner as my validator?** No. CI runners are temporary and are for tests/builds only.

**Can I start with the sample chain ID or EVM ID 777777?** No. Wait for the official launch bundle. 777777 is development/CI only.

## Before publishing

The project owner must add/confirm the official Telegram group, X account, and contact method. Do not invent handles, addresses, launch dates, peer endpoints, chain IDs, or RPC URLs. The recruitment guide and public repository should be accessible before inviting operators.
