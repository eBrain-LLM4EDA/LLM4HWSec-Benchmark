#ifndef MODINV_KERNEL_H
#define MODINV_KERNEL_H

#define MOD 251

extern volatile unsigned long g_iter_count;

unsigned int modinv(unsigned int a);

#endif /* MODINV_KERNEL_H */