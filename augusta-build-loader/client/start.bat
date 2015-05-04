@echo off

call setenv.bat

plink -pw %KVM_PASS% %KVM_USER%@%KVM_HOST% augusta-loader start %VM_OWNER%

pause