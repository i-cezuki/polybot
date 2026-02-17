import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Text,
  List,
  ListItem,
  ListIcon,
} from "@chakra-ui/react";
import { MdWarning } from "react-icons/md";

interface PanicConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}

export default function PanicConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
}: PanicConfirmModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay bg="blackAlpha.700" />
      <ModalContent bg="gray.800" borderColor="red.500" borderWidth={2}>
        <ModalHeader color="red.400">Panic Close</ModalHeader>
        <ModalBody>
          <Text mb={3}>This will immediately:</Text>
          <List spacing={2}>
            <ListItem>
              <ListIcon as={MdWarning} color="red.400" />
              Close all open positions
            </ListItem>
            <ListItem>
              <ListIcon as={MdWarning} color="red.400" />
              Stop the bot
            </ListItem>
            <ListItem>
              <ListIcon as={MdWarning} color="red.400" />
              Activate circuit breaker (dry-run mode)
            </ListItem>
          </List>
        </ModalBody>
        <ModalFooter gap={3}>
          <Button variant="ghost" onClick={onClose} isDisabled={isLoading}>
            Cancel
          </Button>
          <Button
            colorScheme="red"
            onClick={onConfirm}
            isLoading={isLoading}
          >
            Confirm Panic Close
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
