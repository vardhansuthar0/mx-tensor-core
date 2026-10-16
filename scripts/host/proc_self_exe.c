/* Host compatibility for KLayout 0.29.4 in a PID namespace with a host /proc.
 * Translate ONLY /proc/<this process's PID>/exe to /proc/self/exe.
 * No layout, rule-deck, verification, or checker behavior is changed.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
static const char *local_exe(const char *path) {
    char expected[64];
    snprintf(expected,sizeof expected,"/proc/%ld/exe",(long)getpid());
    return path && strcmp(path,expected)==0 ? "/proc/self/exe" : path;
}
int stat(const char *p,struct stat *s) {
    int (*next)(const char *,struct stat *)=dlsym(RTLD_NEXT,"stat");
    return next(local_exe(p),s);
}
int lstat(const char *p,struct stat *s) {
    int (*next)(const char *,struct stat *)=dlsym(RTLD_NEXT,"lstat");
    return next(local_exe(p),s);
}
int stat64(const char *p,struct stat64 *s) {
    int (*next)(const char *,struct stat64 *)=dlsym(RTLD_NEXT,"stat64");
    return next(local_exe(p),s);
}
int lstat64(const char *p,struct stat64 *s) {
    int (*next)(const char *,struct stat64 *)=dlsym(RTLD_NEXT,"lstat64");
    return next(local_exe(p),s);
}
ssize_t readlink(const char *p,char *b,size_t n) {
    ssize_t (*next)(const char *,char *,size_t)=dlsym(RTLD_NEXT,"readlink");
    return next(local_exe(p),b,n);
}
