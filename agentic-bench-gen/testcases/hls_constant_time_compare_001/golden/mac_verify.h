#ifndef MAC_VERIFY_H
#define MAC_VERIFY_H

bool verify(const unsigned char computed_tag[16], const unsigned char received_tag[16]);

#endif // MAC_VERIFY_H