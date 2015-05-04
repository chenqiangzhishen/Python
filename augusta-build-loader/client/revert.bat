@echo off

call setenv.bat

plink -pw %KVM_PASS% %KVM_USER%@%KVM_HOST% augusta-loader revert %VM_OWNER%

pause